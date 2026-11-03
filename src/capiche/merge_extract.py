#!/usr/bin/env python3
#
# merge_extract.py --
#
#       Merge capiche results into the extract section of a PDK's magic tech
#       file.  Only the numbers on existing coefficient lines change.  The type
#       lists, comments, preprocessor conditionals, and every line with no
#       counterpart in the capiche results are left as they are, and the lines
#       left alone are reported.
#
#       The capiche results are the "magic/<stack>.tech" files of the directories
#       <stack>, <stack>_high, and <stack>_low.  They go into the blocks of the
#       extract style that are for the nominal, high capacitance, and low
#       capacitance variants.
#
#       Usage:
#           merge_extract.py <profile> <extract file> [--root <capiche dir>]
#                       [--threshold <ratio>] [--write]
#
#       Without --write, only the report is produced.
#

import argparse
import math
import os
import re
import sys

KEYWORDS = {'defaultareacap': 3, 'defaultperimeter': 3, 'defaultsidewall': 3,
            'defaultoverlap': 5, 'defaultsideoverlap': 5}

# How to read each PDK's extract section:
#   stack:   capiche results used by default
#   branch:  a preprocessor condition whose lines use other results.  The
#            "else" side of the condition uses the default results.
#   skip:    conditions for process variants with no results.  Lines under
#            one of these are left alone.
#   types:   type lists in the tech file with the name used by capiche
PROFILES = {
    'ihp-sg13g2': {'stack': 'ihp-sg13g2'},
    'ihp-sg13cmos5l': {'stack': 'ihp-sg13cmos5l'},
    'sky130': {'stack': 'sky130A', 'branch': {'RERAM': 'sky130B'},
               'types': {'*poly': 'allpoly', 'allpolynonres': 'allpoly',
                         'allpolynonfet': 'allpoly',
                         'allactivenonfet': 'alldifflvnonfet',
                         'allactive': 'alldifflvnonfet'}},
    'gf180mcu': {'stack': 'gf180mcuD', 'skip': ['METALS6'],
                 'types': {'*poly': 'allpoly', 'allpolynonres': 'allpoly',
                           'allpolynonfet': 'allpoly',
                           'alllvactivenonfet': 'alldifflvnonfet',
                           'allmvactivenonfet': 'alldiffmvnonfet'}},
}

CORNERS = {'nominal': '', 'high': '_high', 'low': '_low'}

# Two entries of a type list (such as "nwell,pwell") whose results differ by
# more than this fraction are reported.
LIST_TOLERANCE = 0.005

# Spacing in microns at which sidewall changes are compared in the report
REF_SPACING = 0.25

#--------------------------------------------------------------
# Read the coefficients of one capiche result file into a
# dictionary.  The key is the keyword and type and plane names,
# and the value is the list of numbers.
#--------------------------------------------------------------

def read_results(path):
    results = {}
    in_extract = False
    with open(path) as f:
        for line in f:
            words = line.split()
            if not words or words[0].startswith('#'):
                continue
            if words[0] == 'extract':
                in_extract = True
            elif in_extract and words[0] in KEYWORDS:
                n = KEYWORDS[words[0]]
                results[tuple(words[:n])] = words[n:]
    return results

#--------------------------------------------------------------
# Which results apply to a "variants" line.  Blocks that mix
# nominal with corner variants, or that are for something else,
# are not capiche blocks.
#--------------------------------------------------------------

def corner_of(variants):
    names = set(re.findall(r'\(([^)]*)\)', variants))
    if not names:
        return None
    if names and names <= {'hrhc', 'lrhc'}:
        return 'high'
    if names and names <= {'hrlc', 'lrlc'}:
        return 'low'
    if '' in names and not names & {'hrhc', 'lrhc', 'hrlc', 'lrlc', 'lvs'}:
        return 'nominal'
    return None

#--------------------------------------------------------------
# Find the numbers for a coefficient line, returning them with
# any warning.  An entry of a type list that capiche does not
# have is ignored, as long as another entry is found.
#--------------------------------------------------------------

def lookup(results, words, types):
    n = KEYWORDS[words[0]]
    fields = [[types.get(word, word)] for word in words[1:n]]
    for i, word in enumerate(words[1:n]):
        if ',' in word:
            fields[i] = [types.get(part, part) for part in word.split(',')]
    keys = [(words[0],)]
    for field in fields:
        keys = [key + (name,) for key in keys for name in field]
    found = [results[key] for key in keys if key in results]
    if not found:
        return None, None
    first = float(found[0][0])
    for other in found[1:]:
        if abs(float(other[0]) - first) > LIST_TOLERANCE * abs(first):
            return found[0], ('type list values differ:  %s' %
                        ' '.join(item[0] for item in found))
    return found[0], None

#--------------------------------------------------------------
# The value to compare for a coefficient line.  A sidewall value
# depends on its offset as well as its coefficient, so it is
# compared by its capacitance per length at REF_SPACING.
#--------------------------------------------------------------

def effective(keyword, numbers):
    value = float(numbers[0])
    if keyword == 'defaultsidewall':
        offset = float(numbers[1]) if len(numbers) > 1 else 0.0
        return value / (REF_SPACING + offset)
    return value

#--------------------------------------------------------------
# Replace the numbers of a coefficient line, keeping its
# indentation and the spacing between its other fields.
#--------------------------------------------------------------

def replace_numbers(line, count, numbers):
    match = re.match(r'(\s*' + r'\S+\s+' * count + r')', line)
    return match.group(1) + ' '.join(numbers) + '\n'

#--------------------------------------------------------------
# Merge results into the lines of an extract section.  "results"
# maps (stack, corner) to a dictionary from read_results().
# Returns the new lines and a report.
#--------------------------------------------------------------

def merge(lines, profile, results):
    report = {'changed': [], 'same': 0, 'kept': [], 'warnings': []}
    conditions = []
    variants = None
    in_style = False
    output = []
    types = profile.get('types', {})
    skip = profile.get('skip', [])
    branch = profile.get('branch', {})
    for number, line in enumerate(lines, 1):
        output.append(line)
        match = re.match(r'#(ifdef|ifndef|if|else|elseif|endif)\b\s*(.*)', line)
        if match:
            keyword, text = match.groups()
            if keyword in ('ifdef', 'ifndef', 'if'):
                conditions.append([text.strip(), False])
            elif keyword == 'endif':
                conditions.pop()
            else:
                conditions[-1][1] = True
            continue
        words = line.split()
        if not words or words[0].startswith('#'):
            continue
        if words[0] == 'style':
            in_style = (len(words) > 1) and (words[1] == 'ngspice')
            variants = None
            continue
        if words[0] == 'variants':
            variants = ' '.join(words[1:])
            continue
        if words[0] not in KEYWORDS:
            continue

        corner = corner_of(variants) if (in_style and variants) else None
        label = '%d (%s):  %s' % (number, variants, ' '.join(words))
        if corner is None:
            report['kept'].append(label + '  [not a capiche block]')
            continue
        if any(cond in skip and not is_else for cond, is_else in conditions):
            report['kept'].append(label + '  [variant has no results]')
            continue

        stack = profile['stack']
        for cond, is_else in conditions:
            if cond in branch and not is_else:
                stack = branch[cond]

        numbers, warning = lookup(results[stack, corner], words, types)
        if numbers is None:
            report['kept'].append(label + '  [no result]')
            continue
        if warning:
            report['warnings'].append('%s  [%s]' % (label, warning))

        count = KEYWORDS[words[0]]
        old = words[count:]
        if old == numbers:
            report['same'] += 1
            continue
        output[-1] = replace_numbers(line, count, numbers)
        report['changed'].append((number, variants, ' '.join(words[:count]),
                        effective(words[0], old), effective(words[0], numbers)))
    return output, report

#--------------------------------------------------------------
# Print the report.  Changes of more than the threshold ratio in
# either direction are listed by line.
#--------------------------------------------------------------

def print_report(report, threshold):
    print('Lines changed:  %d;  already equal:  %d;  left alone:  %d' %
                (len(report['changed']), report['same'], len(report['kept'])))
    print('(Sidewall values are compared as aF/um at a spacing of %g um.)' %
                REF_SPACING)
    ratios = {}
    for number, variants, what, old, new in report['changed']:
        if old != 0:
            ratios.setdefault(variants, []).append(new / old)
    for variants, values in ratios.items():
        values.sort()
        print('  %-24s new/old median %.3f, range %.3f to %.3f' %
                (variants, values[len(values) // 2], values[0], values[-1]))
    large = [row for row in report['changed'] if (row[3] == 0) or (row[3] != 0
                and abs(math.log(abs(row[4] / row[3]) or 1e-9)) > math.log(threshold))]
    if large:
        print('Changes larger than a factor of %g:' % threshold)
        for number, variants, what, old, new in large:
            print('  %d (%s):  %s:  %g to %g' % (number, variants, what, old, new))
    if report['warnings']:
        print('Warnings:')
        for warning in report['warnings']:
            print('  ' + warning)
    if report['kept']:
        print('Left alone:')
        for label in report['kept']:
            print('  ' + label)

#--------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Merge capiche results into '
                'the extract section of a magic tech file')
    parser.add_argument('profile', choices=sorted(PROFILES))
    parser.add_argument('extract', help='tech file with the extract section')
    parser.add_argument('--root', default='.', help='capiche directory')
    parser.add_argument('--threshold', type=float, default=1.5)
    parser.add_argument('--write', action='store_true',
                help='write the file (otherwise, only report)')
    args = parser.parse_args()

    profile = PROFILES[args.profile]
    stacks = [profile['stack']] + list(profile.get('branch', {}).values())
    results = {}
    for stack in stacks:
        for corner, suffix in CORNERS.items():
            path = os.path.join(args.root, stack + suffix, 'magic',
                        stack + suffix + '.tech')
            results[stack, corner] = read_results(path)
            if not results[stack, corner]:
                sys.exit('No coefficients found in ' + path)

    with open(args.extract) as f:
        lines = f.readlines()
    output, report = merge(lines, profile, results)
    print_report(report, args.threshold)
    if args.write:
        with open(args.extract, 'w') as f:
            f.writelines(output)
        print('Wrote ' + args.extract)
    else:
        print('Not written (use --write).')

if __name__ == '__main__':
    main()
