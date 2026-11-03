#!/usr/bin/env python3
#
# test_merge_extract.py --
#
#       Tests of merging capiche results into an extract section.
#       Run with:  env PYTHONPATH=src python3 tests/test_merge_extract.py
#

from capiche.merge_extract import corner_of, effective, merge

def results(sidewall, overlap, nwell=None, pwell=None):
    values = {('defaultsidewall', 'allm1', 'metal1'): sidewall,
              ('defaultoverlap', 'allm2', 'metal2', 'allm1', 'metal1'): overlap}
    if nwell:
        values['defaultoverlap', 'allm1', 'metal1', 'nwell', 'well'] = nwell
    if pwell:
        values['defaultoverlap', 'allm1', 'metal1', 'pwell', 'well'] = pwell
    return values

def stack(name, base, **kw):
    return {(name, 'nominal'): results([str(base), '0.1'], [str(base + 1)], **kw),
            (name, 'high'): results([str(base + 2), '0.2'], [str(base + 3)], **kw),
            (name, 'low'): results([str(base + 4), '0.3'], [str(base + 5)], **kw)}

BASIC = """extract
 style ngspice variants (),(hrhc),(lrhc),(hrlc),(lrlc)
variants ()
# defaultsidewall allm1 metal1 1
 defaultsidewall    allm1 metal1  9.9
 defaultoverlap allm2  metal2 allm1 metal1 9.9
 defaultareacap dnwell dwell 120
variants (hrhc),(lrhc)
 defaultsidewall allm1 metal1 9.9
variants (hrlc),(lrlc)
 defaultoverlap allm2 metal2 allm1 metal1 9.9
variants (),(hrhc),(lrhc),(hrlc),(lrlc)
 defaultsidewall allm1 metal1 7.7
variants (lvs)
 defaultsidewall allm1 metal1 8.8
 style pnm
variants ()
 defaultsidewall allm1 metal1 6.6
end
""".splitlines(True)

def check(name, got, want):
    if got != want:
        raise SystemExit('FAIL:  %s\n  got:   %r\n  want:  %r' % (name, got, want))
    print('  ok:  ' + name)

def test_basic():
    output, report = merge(BASIC, {'stack': 's'}, stack('s', 10))
    check('comment left alone', output[3], BASIC[3])
    check('spacing kept, offset added', output[4],
                ' defaultsidewall    allm1 metal1  10 0.1\n')
    check('spacing kept in two-layer line', output[5],
                ' defaultoverlap allm2  metal2 allm1 metal1 11\n')
    check('no result left alone', output[6], BASIC[6])
    check('high', output[8], ' defaultsidewall allm1 metal1 12 0.2\n')
    check('low', output[10], ' defaultoverlap allm2 metal2 allm1 metal1 15\n')
    check('mixed variants left alone', output[12], BASIC[12])
    check('other variants left alone', output[14], BASIC[14])
    check('other style left alone', output[17], BASIC[17])
    check('changes', len(report['changed']), 4)
    again, report = merge(output, {'stack': 's'}, stack('s', 10))
    check('second merge changes nothing', again, output)
    check('second merge counts', (len(report['changed']), report['same']), (0, 4))

def test_branch():
    lines = """ style ngspice variants ()
variants ()
#ifdef RERAM
 defaultsidewall allm1 metal1 9
#else (!RERAM)
 defaultsidewall allm1 metal1 8
#endif (!RERAM)
 defaultoverlap allm2 metal2 allm1 metal1 7
""".splitlines(True)
    data = stack('a', 10)
    data.update(stack('b', 20))
    output, report = merge(lines, {'stack': 'a', 'branch': {'RERAM': 'b'}}, data)
    check('branch side', output[3], ' defaultsidewall allm1 metal1 20 0.1\n')
    check('else side', output[5], ' defaultsidewall allm1 metal1 10 0.1\n')
    check('outside branch', output[7], ' defaultoverlap allm2 metal2 allm1 metal1 11\n')

def test_skip():
    lines = """ style ngspice variants ()
variants ()
#ifdef METALS5 || METALS6
 defaultsidewall allm1 metal1 9
#endif
#ifdef METALS6
 defaultsidewall allm1 metal1 8
#endif
""".splitlines(True)
    output, report = merge(lines, {'stack': 'a', 'skip': ['METALS6']}, stack('a', 10))
    check('condition that includes the variant', output[3],
                ' defaultsidewall allm1 metal1 10 0.1\n')
    check('variant with no results', output[6], lines[6])
    check('reported', len(report['kept']), 1)

def test_types():
    lines = """ style ngspice variants ()
variants ()
 defaultsidewall *m1 metal1 9
 defaultoverlap allm1 metal1 nwell,obswell,pwell well 9
""".splitlines(True)
    profile = {'stack': 'a', 'types': {'*m1': 'allm1'}}
    data = stack('a', 10, nwell=['5.0'], pwell=['5.0'])
    output, report = merge(lines, profile, data)
    check('renamed type', output[2], ' defaultsidewall *m1 metal1 10 0.1\n')
    check('type list', output[3], ' defaultoverlap allm1 metal1 nwell,obswell,pwell well 5.0\n')
    check('no warning', report['warnings'], [])
    data = stack('a', 10, nwell=['5.0'], pwell=['6.0'])
    output, report = merge(lines, profile, data)
    check('different values in a type list are reported', len(report['warnings']), 1)

def test_effective():
    check('sidewall uses its offset', effective('defaultsidewall', ['25', '0.25']), 50.0)
    check('sidewall with no offset', effective('defaultsidewall', ['25']), 100.0)
    check('other keywords use the value', effective('defaultoverlap', ['25']), 25.0)

def test_corners():
    check('nominal', corner_of('(),(orig),(si)'), 'nominal')
    check('high', corner_of('(hrhc),(lrhc)'), 'high')
    check('low', corner_of('(hrlc),(lrlc)'), 'low')
    check('resistor corner', corner_of('(hrhc),(hrlc)'), None)
    check('all variants', corner_of('*'), None)
    check('mixed', corner_of('(),(hrhc),(lrhc),(hrlc),(lrlc)'), None)
    check('lvs', corner_of('(),(lvs)'), None)

if __name__ == '__main__':
    test_basic()
    test_branch()
    test_skip()
    test_types()
    test_effective()
    test_corners()
    print('PASS')
