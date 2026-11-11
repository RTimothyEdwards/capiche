#!/usr/bin/env python3
#
# test_ordered_stack.py --
#
#	Tests of the dielectric stack over a metal used as the reference
#	plane, checked against the series capacitance formula, and of
#	conformal dielectrics stacked around a wire.
#	Run with:  env PYTHONPATH=src python3 tests/test_ordered_stack.py
#

import os
import sys
import tempfile

from capiche.calc_parallel import calc_parallel
from capiche.generate_geometry import generate_one_wire_file
from capiche.generate_geometry_3d import compute_areacap_3d
from capiche.ordered_stack import ordered_stack

EPS0 = 8.854

#--------------------------------------------------------------
# A stack with every kind of dielectric on the lower metal.  The
# variable part is the description of those dielectrics.
#--------------------------------------------------------------

STACK = """
process = 'test'
layers = {{}}
layers['subs'] = ['d', 0.0, 'fox']
layers['fox']  = ['f', 3.9]
layers['m1']   = ['m', 1.0, 0.2, 'fox', 'ild']
{}
layers['ild']  = ['k', 4.0, 'fox']
layers['m2']   = ['m', 2.0, 0.5, 'ild', 'air']
layers['air']  = ['k', 1.0, 'ild']
limits = {{'m1': [0.2, 0.2], 'm2': [0.5, 0.5]}}
"""

#--------------------------------------------------------------
# Return the m2 to m1 area capacitance from calc_parallel() in
# aF/um^2.
#--------------------------------------------------------------

def area_cap(dielectrics, tmpdir):
    stackfile = os.path.join(tmpdir, 'stack.py')
    outfile = os.path.join(tmpdir, 'results.txt')
    with open(stackfile, 'w') as ofile:
        ofile.write(STACK.format(dielectrics))
    assert calc_parallel(stackfile, outfile, 0) == 0
    with open(outfile, 'r') as ifile:
        for line in ifile:
            tokens = line.split()
            if tokens[0] == 'm2' and tokens[1] == 'm1':
                return float(tokens[2])
    raise ValueError('No result for m2 over m1')

#--------------------------------------------------------------
# Return the series capacitance of (thickness, K) pairs.
#--------------------------------------------------------------

def series(*pairs):
    return EPS0 / sum(t / k for (t, k) in pairs)

#--------------------------------------------------------------
# Check the stack entries for a conformal dielectric formed on
# another conformal dielectric around a wire, both with the wire
# metal present and with it absent, and check that both appear
# in the 2D wire geometry.  Return the number of failures.
#--------------------------------------------------------------

def check_stacked_conformal(tmpdir):
    dielectrics = ("layers['c1'] = ['c', 7.0, 0.1, 0.05, 0.1, 'm1']\n" +
		"layers['c2'] = ['c', 5.0, 0.2, 0.06, 0.15, 'c1']")
    locals = {}
    exec(STACK.format(dielectrics), None, locals)
    layers = locals['layers']

    # (name, type, bottom, top with no metal, top with metal, width)
    expected_wire = [('c1', 'c', 1.0, 1.1, 1.3, 0.05),
		('c2', 'c', 1.0, 1.25, 1.5, 0.11)]
    expected_nowire = [('c1', 'k', 1.1, 1.1, 1.1, 0.0),
		('c2', 'k', 1.25, 1.25, 1.25, 0.0)]

    failed = 0
    for (metal, expected) in (('m1', expected_wire), ('m2', expected_nowire)):
        pstack = ordered_stack('subs', [metal], layers)
        entries = {e[0]: e for e in pstack}
        for (name, ltype, bottom, top, mtop, width) in expected:
            e = entries.get(name)
            passed = (e is not None and e[1] == ltype and
			all(abs(a - b) < 1e-9 for (a, b) in
			zip(e[3:7], (bottom, top, mtop, width))))
            print('{}:  {} on {} wire:  {}'.format('PASS' if passed
			else 'FAIL', name, metal, e[1:7] if e else 'missing'))
            if not passed:
                failed += 1

    # Changing the K of either conformal dielectric must change the
    # 2D geometry of the wire.
    decks = []
    lstfile = os.path.join(tmpdir, 'wire.lst')
    for (name, kvalue) in ((None, 0), ('c1', 9.0), ('c2', 9.0)):
        changed = {k: list(v) for (k, v) in layers.items()}
        if name:
            changed[name][1] = kvalue
        generate_one_wire_file(lstfile, 'subs', 'm1', 1.0,
		ordered_stack('subs', ['m1'], changed))
        with open(lstfile, 'r') as ifile:
            decks.append(ifile.read())
    passed = (decks[0] != decks[1]) and (decks[0] != decks[2])
    print('{}:  stacked conformal dielectrics in 2D wire geometry'.format(
		'PASS' if passed else 'FAIL'))
    if not passed:
        failed += 1

    return failed

#--------------------------------------------------------------

def main():
    # The gap between the top of m1 and the bottom of m2 is 0.8um.
    cases = [
	('no dielectric on the metal', '',
		series((0.8, 4.0))),
	('conformal dielectric',
		"layers['c1'] = ['c', 7.0, 0.1, 0.05, 0.1, 'm1']",
		series((0.1, 7.0), (0.7, 4.0))),
	('sidewall dielectric with thickness',
		"layers['s1'] = ['s', 7.5, 0.1, 0.05, 'm1']",
		series((0.1, 7.5), (0.7, 4.0))),
	('sidewall dielectric with no thickness',
		"layers['s1'] = ['s', 3.0, 0, 0.05, 'm1']",
		series((0.8, 4.0))),
	('sidewall on sidewall with no thickness',
		"layers['s1'] = ['s', 3.0, 0, 0.05, 'm1']\n" +
		"layers['s2'] = ['s', 7.5, 0.1, 0.05, 's1']",
		series((0.1, 7.5), (0.7, 4.0))),
	('conformal on sidewall',
		"layers['s1'] = ['s', 3.0, 0.1, 0.05, 'm1']\n" +
		"layers['c1'] = ['c', 7.0, 0.2, 0.05, 0.1, 's1']",
		series((0.1, 3.0), (0.2, 7.0), (0.5, 4.0))),
	('conformal on conformal',
		"layers['c1'] = ['c', 7.0, 0.1, 0.05, 0.1, 'm1']\n" +
		"layers['c2'] = ['c', 5.0, 0.2, 0.05, 0.15, 'c1']",
		series((0.1, 7.0), (0.2, 5.0), (0.5, 4.0))),
    ]

    failed = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        for (name, dielectrics, expected) in cases:
            value = area_cap(dielectrics, tmpdir)

            # The 3D flow takes the same stack
            locals = {}
            exec(STACK.format(dielectrics), None, locals)
            value3d = compute_areacap_3d(ordered_stack('m1', ['m2'], locals['layers']))

            passed = (abs(value / expected - 1) < 1e-3 and
			abs(value3d / expected - 1) < 1e-3)
            print('{}:  {}:  {:.3f} 3D {:.3f} expected {:.3f}'.format(
			'PASS' if passed else 'FAIL', name, value, value3d, expected))
            if not passed:
                failed += 1

        failed += check_stacked_conformal(tmpdir)

    return failed

if __name__ == '__main__':
    sys.exit(main())
