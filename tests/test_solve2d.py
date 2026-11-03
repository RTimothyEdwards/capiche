#!/usr/bin/env python3
#
# test_solve2d.py --
#
#	Tests of the direct 2D capacitance solver against closed-form
#	answers.  Run with:  env PYTHONPATH=src python3 tests/test_solve2d.py
#

import math
import os
import sys
import tempfile

from capiche.solve2d import solve_lst, EPS0

#--------------------------------------------------------------
# Write a 2D input file from a list of main file directives and a
# dictionary of named lists of segments.
#--------------------------------------------------------------

def write_lst(filename, directives, files):
    with open(filename, 'w') as ofile:
        print('* 2D test geometry', file=ofile)
        for directive in directives:
            print(directive, file=ofile)
        print('End', file=ofile)
        for name, segments in files.items():
            print('File ' + name, file=ofile)
            for segment in segments:
                print('S {} {:.6f} {:.6f} {:.6f} {:.6f}'.format(*segment), file=ofile)
            print('End', file=ofile)

#--------------------------------------------------------------
# Check a value in aF/um, and print the result.
#--------------------------------------------------------------

def check(name, value, expected, tolerance):
    error = abs(value / expected - 1)
    passed = (error < tolerance)
    print('{}:  {}:  {:.3f} expected {:.3f} ({:.3f}%)'.format(
		'PASS' if passed else 'FAIL', name, value, expected, 100 * error))
    return passed

#--------------------------------------------------------------
# A cylinder over a ground plane:  C = 2 * pi * eps / acosh(h / a)
#--------------------------------------------------------------

def test_cylinder(directory):
    radius = 0.5
    height = 2.0
    eps = 3.0
    sides = 240
    # Polygon with the same area as the circle
    rpoly = radius * math.sqrt(2 * math.pi / (sides * math.sin(2 * math.pi / sides)))
    points = [(rpoly * math.cos(2 * math.pi * i / sides),
		height + rpoly * math.sin(2 * math.pi * i / sides)) for i in range(sides + 1)]
    segments = [('wire',) + points[i] + points[i + 1] for i in range(sides)]
    filename = os.path.join(directory, 'cylinder.lst')
    write_lst(filename,
		['C wire {} 0 0'.format(eps), 'C plane {} 0 0'.format(eps)],
		{'wire':segments, 'plane':[('ground', -50, 0, 50, 0)]})
    result, _ = solve_lst(filename)
    expected = 2 * math.pi * EPS0 * eps / math.acosh(height / radius)
    return check('cylinder over ground', result[0, 0] * 1e12, expected, 1e-4)

#--------------------------------------------------------------
# The area term of a very wide plate over two dielectric layers:
# C / W = eps0 / (d1 / e1 + d2 / e2).  The slope between two widths
# removes the edges, except for a term that goes as ln(w).
#--------------------------------------------------------------

def plate(directory, width, d1, d2, e1, e2):
    top = d1 + d2
    edge = 5000
    filename = os.path.join(directory, 'plate.lst')
    write_lst(filename,
		['D layer {} {} 0 {} 0 {}'.format(e1, e2, d1, d1 - 0.5),
		'C wire {} 0 0'.format(e2), 'C plane {} 0 0'.format(e1)],
		{'wire':[('wire', -width / 2, top, -width / 2, top + 0.2),
		('wire', -width / 2, top + 0.2, width / 2, top + 0.2),
		('wire', width / 2, top + 0.2, width / 2, top),
		('wire', width / 2, top, -width / 2, top)],
		'layer':[('plane', -edge, 0, edge, 0)],
		'plane':[('ground', -edge, 0, edge, 0)]})
    result, _ = solve_lst(filename)
    return result[0, 0] * 1e12

def test_plate(directory):
    d1, d2, e1, e2 = 0.3, 0.2, 3.9, 7.5
    slope = (plate(directory, 800, d1, d2, e1, e2) - plate(directory, 400, d1, d2, e1, e2)) / 400
    expected = EPS0 / (d1 / e1 + d2 / e2)
    return check('plate over two dielectrics', slope, expected, 2e-3)

#--------------------------------------------------------------
# The reference point of a dielectric, with and without "-", must give
# the same result when outperm and inperm are also exchanged.
#--------------------------------------------------------------

def test_reference(directory):
    results = []
    for directive in ('D layer 3.9 7.5 0 0.3 0 -0.2', 'D layer 7.5 3.9 0 0.3 0 -0.2 -'):
        filename = os.path.join(directory, 'reference.lst')
        write_lst(filename,
		[directive, 'C wire 7.5 0 0', 'C plane 3.9 0 0'],
		{'wire':[('wire', -1, 0.5, -1, 0.7), ('wire', -1, 0.7, 1, 0.7),
		('wire', 1, 0.7, 1, 0.5), ('wire', 1, 0.5, -1, 0.5)],
		'layer':[('plane', -50, 0, 50, 0)],
		'plane':[('ground', -50, 0, 50, 0)]})
        result, _ = solve_lst(filename)
        results.append(result[0, 0] * 1e12)
    return check('dielectric reference side', results[1], results[0], 1e-9)

if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as directory:
        results = [test_cylinder(directory), test_plate(directory), test_reference(directory)]
    sys.exit(0 if all(results) else 1)
