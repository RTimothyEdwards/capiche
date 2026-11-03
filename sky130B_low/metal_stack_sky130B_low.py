#
# metal_stack_sky130B_low.py ---
#
#	Input file for build_fc_files.py.
#	This describes the metal stack for the sky130B process
#	for the low (best) capacitance corner.
#
#	The stack is the hrlc corner of the SkyWater S130 PDK process description
#	(V2.1.302).  ReRAM adds 0.295um between metals 1 and 2, as in sky130B.  Line widths are twice the capacitance
#	wire edge enlargement of that corner.
#
#	sky130B has ReRAM support.  The ReRAM layers are placed between
#	metals 1 and 2, so the entire metal stack above metal 1 is raised
#	with respect to sky130A.
#
process = 'sky130B_low'	# Process name
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
layers['diff']   = ['d', 0.4261, 'fox']
layers['mvdiff'] = ['d', 0.4183, 'fox']
layers['fox']    = ['f', 3.9] 
layers['poly']   = ['m', 0.4293, 0.1600, 'fox', 'psg']
layers['iox']    = ['s', 3.9, 0, 0.006, 'poly']
layers['spnit']  = ['s', 7.5, 0.1065, 0.0431, 'iox']
layers['psg']    = ['k', 3.9, 'fox']
layers['li']     = ['m', 1.1770, 0.0800, 'psg', 'lint']
layers['lint']   = ['c', 7.3, 0.0675, 0.0548, 0.0675, 'li']
layers['nild2']  = ['k', 3.90, 'lint']
layers['m1']     = ['m', 1.7295, 0.3300, 'nild2', 'nild3']
layers['nild3c'] = ['s', 3.3, 0, 0.04, 'm1']
layers['nild3']  = ['k', 4.50, 'nild2']
layers['m2']     = ['m', 2.7845, 0.3300, 'nild3', 'nild4']
layers['nild4c'] = ['s', 3.3, 0, 0.04, 'm2']
layers['nild4']  = ['k', 3.90, 'nild3']
layers['m3']     = ['m', 3.6955, 0.7650, 'nild4', 'nild5']
layers['nild5']  = ['k', 3.90, 'nild4']
layers['m4']     = ['m', 5.0075, 0.7650, 'nild5', 'nild6']
layers['nild6']  = ['k', 4.00, 'nild5']
layers['m5']     = ['m', 6.4345, 1.1340, 'nild6', 'topox']
layers['topox']  = ['s', 3.9, 0.1031, 0.0801, 'm5'] 
layers['topnit'] = ['c', 7.5, 0.6482, 0.3374, 0.3020, 'topox']
layers['air']    = ['k', 2.94, 'topnit']

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
linebias['li'] = -0.0230
linebias['m1'] = -0.0206
linebias['m2'] = -0.0206
linebias['m3'] = +0.0320
linebias['m4'] = +0.0320
linebias['m5'] = -0.1000

#
# Sidewall coefficients that replace the solver's result.  These are fits to
# the coupling values at or below 2um spacing in parameters/fast.spice in the
# SPICE models.  Near minimum pitch, those values are well below what a solid
# dielectric gives.

sidewalloverride = {}
sidewalloverride['m1'] = [47.83, 0.376]
sidewalloverride['m2'] = [52.84, 0.433]
sidewalloverride['m3'] = [84.96, 0.625]
sidewalloverride['m4'] = [93.14, 0.713]

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

