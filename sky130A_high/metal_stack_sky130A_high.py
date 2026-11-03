#
# metal_stack_sky130A_high.py ---
#
#	Input file for build_fc_files.py.
#	This describes the metal stack for the sky130A process
#	for the high (worst) capacitance corner.
#
#	The stack is the lrhc corner of the SkyWater S130 PDK process description
#	(V2.1.302).  Line widths are twice the capacitance
#	wire edge enlargement of that corner.
#
process = 'sky130A_high'	# Process name
feature_size = 0.15	# process minimum gate length (for general scaling)

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
layers['diff']   = ['d', 0.2199, 'fox']
layers['mvdiff'] = ['d', 0.2121, 'fox']
layers['fox']    = ['f', 3.9] 
layers['poly']   = ['m', 0.2231, 0.2000, 'fox', 'psg']
layers['iox']    = ['s', 3.9, 0, 0.006, 'poly']
layers['spnit']  = ['s', 7.5, 0.1525, 0.0431, 'iox']
layers['psg']    = ['k', 3.9, 'fox']
layers['li']     = ['m', 0.6917, 0.1150, 'psg', 'lint']
layers['lint']   = ['c', 7.3, 0.0825, 0.0668, 0.0825, 'li']
layers['nild2']  = ['k', 3.90, 'lint']
layers['m1']     = ['m', 1.0137, 0.3900, 'nild2', 'nild3']
layers['nild3']  = ['k', 4.30, 'nild2']
layers['m2']     = ['m', 1.5137, 0.3900, 'nild3', 'nild4']
layers['nild4']  = ['k', 4.20, 'nild3']
layers['m3']     = ['m', 2.1629, 0.9250, 'nild4', 'nild5']
layers['nild5']  = ['k', 4.10, 'nild4']
layers['m4']     = ['m', 3.2679, 0.9250, 'nild5', 'nild6']
layers['nild6']  = ['k', 4.10, 'nild5']
layers['m5']     = ['m', 4.4889, 1.3860, 'nild6', 'topox']
layers['topox']  = ['s', 3.9, 0.0769, 0.0597, 'm5'] 
layers['topnit'] = ['c', 7.5, 0.4318, 0.5065, 0.4534, 'topox']
layers['air']    = ['k', 3.50, 'topnit']

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
# Difference between manufactured and drawn line width, by layer

linebias = {}
linebias['li'] = +0.0230
linebias['m1'] = +0.0206
linebias['m2'] = +0.0206
linebias['m3'] = +0.0280
linebias['m4'] = +0.0280

#
# Sidewall coefficients that replace the solver's result.  These are fits to
# the coupling values at or below 2um spacing in parameters/slow.spice in the
# SPICE models.  Near minimum pitch, those values are well below what a solid
# dielectric gives.

sidewalloverride = {}
sidewalloverride['m1'] = [42.39, 0.165]
sidewalloverride['m2'] = [46.72, 0.199]
sidewalloverride['m3'] = [82.20, 0.360]
sidewalloverride['m4'] = [97.40, 0.473]

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

# Optional - automatic tech file generation for magic

magicplanes = {}
magicplanes['subs'] = 'well'
magicplanes['nwell'] = 'well'
magicplanes['diff'] = 'active'
magicplanes['mvdiff'] = 'active'
magicplanes['poly'] = 'active'
magicplanes['li'] = 'locali'
magicplanes['m1'] = 'metal1'
magicplanes['m2'] = 'metal2'
magicplanes['m3'] = 'metal3'
magicplanes['m4'] = 'metal4'
magicplanes['m5'] = 'metal5'

magicaliases = {}
magicaliases['subs'] = None
magicaliases['nwell'] = None
magicaliases['diff'] = 'alldifflvnonfet'
magicaliases['mvdiff'] = 'alldiffmvnonfet'
magicaliases['poly'] = 'allpoly'
magicaliases['li'] = 'allli'
magicaliases['m1'] = 'allm1'
magicaliases['m2'] = 'allm2'
magicaliases['m3'] = 'allm3'
magicaliases['m4'] = 'allm4'
magicaliases['m5'] = 'allm5'

magicstyles = {}
magicstyles['subs'] = 'pwell'
magicstyles['nwell'] = 'nwell'
magicstyles['diff'] = 'ndiffusion'
magicstyles['mvdiff'] = 'ndiffusion'
magicstyles['poly'] = 'polysilicon'
magicstyles['li'] = 'metal1'
magicstyles['m1'] = 'metal2'
magicstyles['m2'] = 'metal3'
magicstyles['m3'] = 'metal4'
magicstyles['m4'] = 'metal5'
magicstyles['m5'] = 'metal6'

