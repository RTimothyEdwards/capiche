#!/usr/bin/env python3

# Entry point for capiche

import argparse

from compute_coefficients import compute_coefficients


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        prog='capiche',
        description='A system for analyzing foundry metal stackups using FasterCap',
        epilog='https://github.com/RTimothyEdwards/capiche/')
    
    # Add arguments
    parser.add_argument('stack_def_file', type=str, help='Stack definition file')
    parser.add_argument('magic_startup_file', type=str, nargs='?', help="Instead of using the auto-generated magic startup file, use the provided one")
    
    parser.add_argument('-noshield', action='store_false', help='Do not run fringe shield simulations')
    parser.add_argument('-nopartial', action='store_false', help='Do not run partial fringe simulations')
    parser.add_argument('-nosidewall', action='store_false', help='Do not run sidewall simulations')
    
    parser.add_argument('-verbose', type=int, default=0, help='Diagnostic level')
    
    # Parss the arguments
    args = parser.parse_args()

    # Compute the coefficients
    compute_coefficients(args.stack_def_file, args.magic_startup_file, not args.noshield, not args.nopartial, not args.nosidewall, args.verbose)

    # Exit
    sys.exit(0)
