#
# metal_stack_sky130A.py ---
#
#	Input file for build_fc_files.py.
#	This describes the metal stack for the sky130A process
#
process = 0.15	;# process minimum gate length (for general scaling)

# Well/substrate is assumed to define Y = 0.
# All dimension values are in microns
#
# Layer types:
# 'd':  diffusion.  Defines the ground plane (conducting layer), which may
#	be the substrate, well, or diffusion.  Has two arguments;  the
#	first argument is a height value of the top of the diffusion/well/
#	substrate.  The second is the name of the dielectric type above
#	the ground plane.  Several diffusion/well/substrate types may be
#	declared, but only one can be used in any given output file.
# 'k':	dielectric.  Has two arguments, which are dielectric constant and
#	the name of the dielectric layer underneath it.  Thickness varies
#	according to presence or absence of the metal or a conforming
#	dielectric.
# 'f':  field oxide dielectric.  Has one argument, which is the dielectric
#	constant.  The associated layer is always either well or diffusion,
#	and separate tables will be generated for both cases.
# 'c':	conforming dielectric.  Has five arguments, which are dielectric
#	constant, thickness above the associated layer, sidewall width,
#	thickness when not over the associated layer, and an associated
#	metal or dielectric layer.  Thickness is constant, but height will
#	vary according to presence or absence of a coincident metal layer.
#	The dielectric underneath is assumed to be the same as the dielectric
#	underneath the associated layer.
# 's':	sidewall dielectric.  Has four arguments, which are dielectric
#	constant, thickness, sidewall width, and associated metal layer.
#	Thickness is constant, but height will vary according to presence
#	or absence of a coincident metal layer.  The dielectric underneath
#	is assumed to be the same as the dielectric underneath the associated
#	metal layer.  Sidewall dielectrics are just conforming dielectrics
#	with no thickness except above the associated metal layer.
# 'm':  Metal (conductor) layer.  Has four arguments, which are the layer
#	height and layer thickness, the dielectric layer underneath, and
#	the dielectric layer on top (and on the sides, if there is no
#	associated conformal dielectric).  Includes any conductor such as
#	poly, local interconnect, etc.

layers = {}
layers['subs']	 = ['d', 0.0000, 'fox']
layers['nwell']  = ['d', 0.0000, 'fox']
layers['diff']   = ['d', 0.3230, 'fox']
layers['mvdiff'] = ['d', 0.3152, 'fox']
layers['fox']    = ['f', 3.9] 
layers['poly']   = ['m', 0.3262, 0.18, 'fox', 'psg']
layers['iox']    = ['s', 3.9, 0, 0.006, 'poly']
layers['spnit']  = ['s', 7.5, 0.121, 0.0431, 'iox']
layers['psg']    = ['k', 3.9, 'fox']
layers['li']     = ['m', 0.9361, 0.10, 'psg', 'lint']
layers['lint']   = ['c', 7.3, 0.075, 0.075, 0.075, 'li']
layers['nild2']  = ['k', 4.05, 'lint']
layers['m1']     = ['m', 1.3761, 0.36, 'nild2', 'nild3']
layers['nild3c'] = ['s', 3.5, 0, 0.03, 'm1']
layers['nild3']  = ['k', 4.5, 'nild2']
layers['m2']     = ['m', 2.0061, 0.36, 'nild3', 'nild4']
layers['nild4c'] = ['s', 3.5, 0, 0.03, 'm2']
layers['nild4']  = ['k', 4.2, 'nild3']
layers['m3']     = ['m', 2.7861, 0.845, 'nild4', 'nild5']
layers['nild5']  = ['k', 4.1, 'nild4']
layers['m4']     = ['m', 4.0211, 0.845, 'nild5', 'nild6']
layers['nild6']  = ['k', 4.0, 'nild5']
layers['m5']     = ['m', 5.3711, 1.26, 'nild6', 'topox']
layers['topox']  = ['s', 3.9, 0.09, 0.07, 'm5'] 
layers['topnit'] = ['c', 7.5, 0.54, 0.4223, 0.3777, 'topox']
layers['air']    = ['k', 1.0, 'topnit']

#
# Define metal width and spacing minimum limits.
# There must be one entry for each layer type 'm' defined above.
# 1st value is minimum width, 2nd value is minimum spacing

limits = {}
limits['poly'] = [0.15, 0.21]
limits['li']   = [0.17, 0.17]
limits['m1']   = [0.14, 0.14]
limits['m2']   = [0.14, 0.14]
limits['m3']   = [0.3,  0.3]
limits['m4']   = [0.3,  0.3]
limits['m5']   = [1.6,  1.6]

#
# Define the (known and agreed-upon) parallel plate capacitance
# 4 values are cap to substrate, nwell, lv-diffusion, and mv-diffusion
# (NOTE: This section is optional.  Plate capacitances are computed
# directly)

platecap = {}
platecap['poly'] = [106.13, 106.13, 10791, 3139.1 ]
platecap['li']   = [ 36.99,  36.99,  55.3,  54.6 ]
platecap['m1']   = [ 25.78,  25.78,  33.6,  33.4 ]
platecap['m2']   = [ 17.50,  17.50,  20.8,  20.7 ]
platecap['m3']   = [ 12.37,  12.37,  14.2,  14.2 ]
platecap['m4']   = [  8.42,   8.42,  9.41,   9.39]
platecap['m5']   = [  6.32,   6.32,  6.88,   6.87]

#
# Define the relationship between metal layers in this file
# and layers in magic (for use with magic extraction)

magiclayers = {}
magiclayers['subs'] = 'pwell'
magiclayers['nwell'] = 'nwell'
magiclayers['diff'] = 'ndiff'
magiclayers['mvdiff'] = 'mvndiff'
magiclayers['poly'] = 'poly'
magiclayers['li'] = 'li'
magiclayers['m1'] = 'm1'
magiclayers['m2'] = 'm2'
magiclayers['m3'] = 'm3'
magiclayers['m4'] = 'm4'
magiclayers['m5'] = 'm5'
