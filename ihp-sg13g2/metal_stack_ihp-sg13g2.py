#
# metal_stack_ihp-sg13g2.py ---
#
#	Input file for build_fc_files.py.
#	This describes the metal stack for the ihp-sg13g2 process
#
process = 'ihp-sg13g2'	# Process name
feature_size = 0.13	# process minimum gate length (for general scaling)

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
# 'b':  boundary dielectric.  Has three arguments, which are the height
#	above the substrate, dielectric constant, and the name of the
#	dielectric layer beneath it.  Like 'k', but used when a dielectric
#	layer is added that has no relationship to a metal underneath.
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

# https://github.com/IHP-GmbH/IHP-Open-PDK/blob/main/ihp-sg13g2/libs.doc/doc/SG13G2_os_process_spec.pdf

layers = {}
layers['subs']	 = ['d', 0.0000, 'fox']
layers['nwell']  = ['d', 0.0000, 'fox']
# LV gate oxide is 2.65nm
layers['diff']   = ['d', 0.4 - 0.00245, 'fox']
# HV gate oxide is 7.5nm
layers['hvdiff'] = ['d', 0.4 - 0.0073, 'fox']
layers['fox']    = ['f', 3.95]

layers['gatpoly'] = ['m', 0.4, 0.16, 'fox', 'nit']
layers['nit']     = ['c', 6.5, 0.05, 0.05, 0.05, 'gatpoly']
layers['ild']     = ['k', 4.1, 'nit']

layers['metal1'] = ['m', 0.4 + 0.64, 0.42, 'ild', 'imd1']
layers['imd1']   = ['k', 4.1, 'ild']

layers['metal2'] = ['m', 0.4 + 0.64 + (0.42 + 0.54), 0.49, 'imd1', 'imd2']
layers['imd2']   = ['k', 4.1, 'imd1']

layers['metal3'] = ['m', 0.4 + 0.64 + (0.42 + 0.54) + (0.49 + 0.54), 0.49, 'imd2', 'imd3']
layers['imd3']   = ['k', 4.1, 'imd2']

layers['metal4'] = ['m', 0.4 + 0.64 + (0.42 + 0.54) + (0.49 + 0.54) * 2, 0.49, 'imd3', 'imd4']
layers['imd4']   = ['k', 4.1, 'imd3']

layers['metal5'] = ['m', 0.4 + 0.64 + (0.42 + 0.54) + (0.49 + 0.54) * 3, 0.49, 'imd4', 'imd5']
layers['imd5']   = ['k', 4.1, 'imd4']

layers['topmetal1'] = ['m', 0.4 + 0.64 + (0.42 + 0.54) + (0.49 + 0.54) * 3 + (0.49 + 0.85), 2.0, 'imd5', 'imd6']
layers['imd6']      = ['k', 4.1, 'imd5']

layers['topmetal2'] = ['m', 0.4 + 0.64 + (0.42 + 0.54) + (0.49 + 0.54) * 3 + (0.49 + 0.85) + (2.0 + 2.8), 3.0, 'imd6', 'pass']
layers['imd7']      = ['c', 4.1, 1.5, 0.3, 1.5, 'imd6']
layers['pass']      = ['c', 6.6, 0.4, 0.3, 0.4, 'imd7']
layers['air']       = ['k', 3.0, 'pass']

#
# Define metal width and spacing minimum limits.
# There must be one entry for each layer type 'm' defined above.
# 1st value is minimum width, 2nd value is minimum spacing

# https://github.com/IHP-GmbH/IHP-Open-PDK/blob/main/ihp-sg13g2/libs.doc/doc/SG13G2_os_layout_rules.pdf

limits = {}
# 5.8 GatPoly
limits['gatpoly'] = [0.13, 0.18]
# 5.16 Metal1
limits['metal1'] = [0.16, 0.18]
# 5.17 Metal2-5
limits['metal2'] = [0.20, 0.21]
limits['metal3'] = [0.20, 0.21]
limits['metal4'] = [0.20, 0.21]
limits['metal5'] = [0.20, 0.21]
# 5.22 TopMetal1
limits['topmetal1'] = [1.64, 1.64]
# 5.25 TopMetal2
limits['topmetal2'] = [2.0, 2.0]

#
# Define the relationship between metal layers in this file
# and layers in magic (for use with magic extraction)

magiclayers = {}
magiclayers['subs'] = 'pwell'
magiclayers['nwell'] = 'nwell'
magiclayers['diff'] = 'ndiff'
magiclayers['hvdiff'] = 'hvndiff'
magiclayers['gatpoly'] = 'poly'
magiclayers['metal1'] = 'm1'
magiclayers['metal2'] = 'm2'
magiclayers['metal3'] = 'm3'
magiclayers['metal4'] = 'm4'
magiclayers['metal5'] = 'm5'
magiclayers['topmetal1'] = 'm6'
magiclayers['topmetal2'] = 'm7'

# Optional - automatic tech file generation for magic

magicplanes = {}
magicplanes['subs'] = 'well'
magicplanes['nwell'] = 'well'
magicplanes['diff'] = 'active'
magicplanes['hvdiff'] = 'active'
magicplanes['gatpoly'] = 'active'
magicplanes['metal1'] = 'metal1'
magicplanes['metal2'] = 'metal2'
magicplanes['metal3'] = 'metal3'
magicplanes['metal4'] = 'metal4'
magicplanes['metal5'] = 'metal5'
magicplanes['topmetal1'] = 'metal6'
magicplanes['topmetal2'] = 'metal7'

magicaliases = {}
magicaliases['subs'] = None
magicaliases['nwell'] = None
magicaliases['diff'] = 'alldifflvnonfet'
magicaliases['hvdiff'] = 'alldiffhvnonfet'
magicaliases['gatpoly'] = 'allpoly'
magicaliases['metal1'] = 'allm1'
magicaliases['metal2'] = 'allm2'
magicaliases['metal3'] = 'allm3'
magicaliases['metal4'] = 'allm4'
magicaliases['metal5'] = 'allm5'
magicaliases['topmetal1'] = 'allm6'
magicaliases['topmetal2'] = 'allm7'

magicstyles = {}
magicstyles['subs'] = 'pwell'
magicstyles['nwell'] = 'nwell'
magicstyles['diff'] = 'ndiffusion'
magicstyles['hvdiff'] = 'ndiffusion'
magicstyles['gatpoly'] = 'polysilicon'
magicstyles['metal1'] = 'metal1'
magicstyles['metal2'] = 'metal2'
magicstyles['metal3'] = 'metal3'
magicstyles['metal4'] = 'metal4'
magicstyles['metal5'] = 'metal5'
magicstyles['topmetal1'] = 'metal6'
magicstyles['topmetal2'] = 'metal7'

