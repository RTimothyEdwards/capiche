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
#	2.  layer height above y=0 over field
#	3.  layer height above y=0 over wire
#	4.  layer offset in x direction (or 0 if not applicable)
#	5.  layer dielectric constant (or 0 if a conductor)
# --------------------------------------------------------

def ordered_stack(substrate, metals, layers):
    pstack = []		# An ordered list, not a dictionary

    # First find the appropriate reference plane conductor and
    # put at first position in list.  A metal can be used as the
    # reference conductor (with the conductor position at the top
    # of the metal layer)

    height = 0.0
    for lname, layer in layers.items():
        if lname == substrate:
            if layer[0] == 'd':
                pstack.append([lname, 'd', layer[1], layer[1], 0.0, 0])
                break
            elif layer[0] == 'm':
                lheight = layer[1] + layer[2]
                pstack.append([lname, 'd', lheight, lheight, 0.0, 0])
                break

    yref = layer[1]

    # Work from bottom to top of the stack.  Stop when there are no more
    # metals.  This is inefficient, but the metal stack is not large.

    while (True):
        # Find the lowest metal higher than yref.
        minmy = 10000
        for lname, layer in layers.items():
            if layer[0] == 'm':
                if layer[1] > yref and layer[1] < minmy:
                    minmy = layer[1]
                    minmn = lname

        if minmy == 10000:
            break

        # Set yref to the metal layer height
        yref = minmy
        # The reference width value starts at zero for each planar metal layer
        wref = 0.0

        # Diagnostic
        # height = "{:.4f}".format(minmy)
        # print('Forming stack:  Reference metal is ' + minmn + ' height ' + height)

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
        pstack.append([lname, 'k', yref, yref, 0.0, klayer[1]])

        if usemetal == True:
            # The reference Y value is now at the top of the metal
            yref += mlayer[2]

            pstack.append([minmn, 'm', yref, yref, 0.0, 0])

            # If there is a sidewall associated with the metal, then add it
            for sname, slayer in layers.items():
                if slayer[0] == 's':
                    if slayer[4] == minmn:
                        wref += slayer[3]
                        pstack.append([sname, 's', minmy,
				yref + slayer[2], wref, slayer[1]])
                        yref += slayer[2]
                        break

            # If there is a second sidewall associated with the first, then
            # add it
            for ssname, sslayer in layers.items():
                if sslayer[0] == 's':
                    if sslayer[4] == sname:
                        wref += sslayer[3]
                        pstack.append([ssname, 'c', minmy,
				yref + sslayer[2], wref, sslayer[1]])
                        yref += sslayer[2]
                        break

            # If there is a conformal dielectric associated with the sidewall,
            # then add it.
            for cname, clayer in layers.items():
                if clayer[0] == 'c':
                    if clayer[5] == sname:
                        wref += clayer[3]
                        pstack.append([cname, 'c', minmy + clayer[4],
				yref + clayer[2], wref, clayer[1]])
                        yref += clayer[2]

            # If there is a conformal dielectric associated with the metal,
            # then add it.
            for cname, clayer in layers.items():
                if clayer[0] == 'c':
                    if clayer[5] == minmn:
                        wref += clayer[3]
                        pstack.append([cname, 'c', minmy + clayer[4],
				yref + clayer[2], wref, clayer[1]])
                        yref += clayer[2]
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
                        yref += clayer[2]
                        pstack.append([cname, 'k', yref, yref, 0.0, clayer[1]])
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
                            yref += clayer[2]
                            pstack.append([cname, 'k', yref, yref, 0.0, clayer[1]])
                            break


    # Add the entry for "air" (k=1.0) to the top.
    for lname, layer in layers.items():
        if layer[0] == 'k':
            if lname == 'air':
                pstack.append([lname, 'k', 'inf', 'inf', wref, 1.0])
                break

    # Reverse the order so that the list is from top to bottom
    pstack.reverse()

    return pstack

#--------------------------------------------------------------
