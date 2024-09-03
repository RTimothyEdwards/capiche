# capiche:  A system for analyzing foundry metal stackups using FasterCap

- Author: Tim Edwards
- Initial version: January 6, 2023
- Updates:

  - **January 12, 2023:**  Corrected some errors in FasterCap input
    files, including breaking out separate left and right segments
    for metal wires that have sidewall dielectric.  Corrected the
    handling of TOPOX over metal 5 in sky130A, which was previously
    capturing the sidewall but not the dielectric above the metal.

  - **January 29, 2023:**  Additional errors in FasterCap intput
    files based on feedback from the FasterCap developer.


## Requirements:

- python3
  - with packages numpy, scipy, and matplotlib
- [FasterCap](https://github.com/ediloren/FasterCap)
  - [LinAlgebra](https://github.com/ediloren/LinAlgebra)
  - [Geometry](https://github.com/ediloren/Geometry)
- [magic](https://github.com/RTimothyEdwards/magic)
- [open_pdks](https://github.com/RTimothyEdwards/open_pdks) or [volare](https://github.com/efabless/volare) (installed for sky130 and/or gf180mcu processes)

## Usage:

	./compute_coefficients.py  sky130A/metal_stack_sky130A.py
	./compute_coefficients.py  gf180mcuD/metal_stack_gf180mcuD.py

> [!NOTE]  
> If FasterCap isn't in the standard execution path, set the environment
variable `FASTERCAP_EXEC` to the full path of FasterCap.

> [!NOTE]  
> If magic isn't in the standard execution path, set the environment
variable `MAGIC_EXEC` to the full path of magic.

> [!NOTE]  
> If the PDK is not installed in the default `/usr/local/share/` or commonly
used `/usr/share/` directories, then pass the location of the PDK `.magicrc`
startup file as the 2nd argument to `compute_coefficients.py` (see the
open_pdks installation instructions for more information).

Add option `-verbose=1` for more output, or `-verbose=2` for considerably
more output.

This will run for a long time[^1], generating metal wire configurations
and running them through FasterCap to generate coupling capacitance
estimations for each geometry.  Once the data files containing all of
the coupling capacitance tables have been generated, capiche will
solve for coefficients to analytic solutions of parasitic capacitance,
and generate plots of the FasterCap results vs. results extracted
using the program [magic](https://github.com/RTimothyEdwards/magic)
and the analytic expressions computed using the calculated coefficients.

[^1]: Around 12 hours on a modern 16-core processor, e.g., Intel core-i9
  Results are saved, so that subsequent runs will not repeat the
  FasterCap runs if the output files exist.  Most of the time is
  spent running FasterCap.


Most output is in the form of capacitance tables and SVG format plots.

The main output file is `<pdk_name>/analysis/coefficients.txt`
listing the following coefficients:

1. `areacap <metal> <conductor> <value>`

	The parallel plate capacitance in aF/um^2 between
	the bottom of metal layer `<metal>` and the top of
	conductor layer `<conductor>`, which may be a metal or
	a substrate type.

2. `fringecap <metal> <conductor> <value>`

	The maximum fringe capacitance per edge length in aF/um
	between `<metal>` and `<conductor>`, where `<conductor>` may
	be another metal layer above or below `<metal>`, or a
	substrate type.  The `<conductor>` is treated as an
	effectively infinite surface in all directions.

3. `sidewall <metal> <value> <offset>`

	The value of sidewall coupling capacitance per unit
	length satisfying the analytical expression

		Ccoup = <value> / (separation + <offset>)

	Where `<value>` is in aF/um and `<offset>` is in um.

4. `fringeshield <metal> <conductor> <multiplier> <offset>`

	The fraction of fringe capacitance shielded by a
	nearby wire on the same plane as `<metal>` with
	both wires placed over a large plane of material
	`<conductor>`.  The coefficients are used in the
	following analytic expression for fringe shielding:

		Cfrac = tanh(<multiplier> * (separation + <offset>))

	Where `<multiplier>` is unitless and `<offset>` is in um.
	"separation" is the distance from the edge of `<metal>`
	to the edge of the nearby wire of the same metal type.
	Cfrac represents the *unshielded* portion of the fringe
	capacitance.

5. `fringepartial <metal> <conductor> <multiplier> <offset>`

	The fraction of fringe capacitance of `<metal>` incident
	upon another layer `<conductor>` (which may be a metal
	layer or substrate type) from the edge of `<metal>` out
	to a given distance.  The coefficients are used in the
	following analytic expression for the partial fringe:

		Cfrac = (2/pi)*arctan(<multiplier> * (distance + <offset>))

	Where `<multiplier>` is unitless and `<offset>` is in um.
	Cfrac represents the portion of the maximum fringe
	capacitance (i.e., item (2) above) seen on `<conductor>`
	from the metal edge out to distance "distance".

---

Plots are made of the data taken for items (3), (4), and (5)
above.  Each plot has three components:

1. The measurements obtained from FasterCap analysis
2. The best-fit curve for the analytic expressions discussed above
3. The measurements obtained from extracted layout in magic

Plots can be found in:

- `<pdk_name>/plots/sidewall`	for item (3) above
- `<pdk_name>/plots/fringeshield`	for item (4) above
- `<pdk_name>/plots/fringepartial`	for item (5) above

Note that as of the first version of Capiche, magic encodes
models of fringe shielding and partial fringing that are different
from the analytical expressions described above.  This is to be
expected, as the purpose of Capiche is to improve the models used
in magic (see "work to do", below).

## Input file format:

The main input file to Capiche is a python script that describes
a process metal and dielectric stack.  The file

	sky130A/metal_stack_sky130A.py

is provided as a complete example, and describes the metal stack
of the SkyWater sky130 process with options as selected for the
open_pdks process variant name "sky130A" (which is 6 metal layers;
see open_pdks for more information).  Any process can be described
with a similar file, which needs to encode a number of values in
Python variable form, as described below.  The file is evaluated
in Python line by line, so any valid Python syntax is allowed.
However, Capiche Python scripts will only expect and use the
following variables:

	process = '<pdk_name>'

where <pdk_name> is a name given to the process (e.g., "sky130A").
This name will be used as the directory top level for all files
and data generated by Capiche for the process.  If the name matches
an open_pdks technology variant name (e.g., "sky130A"), then it
will also be used to automatically find the magic tech file for the
process.

	layers['<layer_name>'] = ['<type>', <values>. . .]

This is the main metal and dielectric stackup information.  There
are six types recognized by the single-letter <type>.  The type
of layer determines what the remaining <values> items in the list
must be.  The layer types are as follows:

	'd':	Diffusion type, used for substrate, well, or diffusion
	'f':	Field oxide type, which is directly above the substrate
	'k':	Simple dielectric
	'b':	Simple dielectric unrelated to any metal
	'c':	Conformal dielectic
	's':	Sidewall dielectric
	'm':	Metal

Layers may be listed in any order, although obviously a bottom-to-top
or top-to-bottom format will be easier to read and understand.  Every
layer stack must have one layer called 'air' representing the area
above the highest manufactured layer in the process.  All other layer
names are arbitrary and should be chosen to be meaningful within the
context of the process.

The list entries for each of the types above are as follows:

	['d', <height>, <reference>]

where `<height>` is the height above the substrate (assumed to be at
zero height), and `<reference>` is the name of the dielectric layer
immediately above the layer (normally field oxide).

	['f', <K_value>]

This entry is for the field oxide.  This is like other dielectrics,
but the field oxide is always referenced to the substrate, so it has
only a single value, which is the dielectric K coefficient (a
dimensionless unit which is multiplied by the permitivity of vacuum)

	['k', <K_value>, <reference>]

This is a simple dielectric boundary.  All planes in a fabrication
process are assumed to be dictated by each metal layer, so dielectric
boundaries do not need to define a layer hight.  They are simply
referenced to the dielectric layer name `<reference>` of the dielectric
directly below the layer.  The `<K_value>` is the dielectric K constant.

	['c', <K_value>, <thick1>, <thick2>, <thick3>, <reference>]

This is a conformal dielectric which is formed around a metal layer
and forms a layer above and around the metal.  `<K_value>` is the
dielectric K constant of the layer.  `<thick1>` is the thickness of
the dielectric over metal, while `<thick2>` is the thickness of the
dielectric where the metal is not present.  `<thick3>` is the sidewall
thickness of the dielectric.  The `<reference>` layer is always a
metal.

	['s', <K_value>, <thick1>, <thick2>, <reference>]

This is a sidewall dielectric which is formed around a metal layer
but does not exist away from the metal.  `<thick1>` is the height
of the layer above the metal, and may be zero if the dielectric is
only on the metal sidewall and does not exist on top of the metal.
`<thick2>` is the width of the dielectric from the metal sidewall
outward.  The `<reference>` layer is always a metal.

	['m', <height>, <thick>, <ref_below>, <ref_above>]

This entry represents a metal (where "metal" is taken to mean any
conductor layer that is not a substrate type, and so includes
layers like polysilicon or titanium nitride interconnect).
`<height>` is the height of the metal above the substrate, in microns,
and `<thick>` is thickness of the metal, also in microns.  The
layer name `<ref_below>` is the dielectric underneath the metal, and
the layer name `<ref_above>` is the dielectric above the metal.
The `<ref_above>` is always the layer directly on top of the metal.
If a sidewall has a non-zero `<thick1>` value, then it is the
dielectric used for `<ref_above>`.  If there is a sidewall dielectric
with zero `<thick1>` and there is a secondary sidewall with nonzero
`<thick1>` or a conformal dielectric present, then that layer would
be used as `<ref_above>`.
	
	limits['<layer_name>'] = [<minwidth>, <minspace>]

This variable is used to declare the minimum width and minimum
space (in micron units) for each metal layer.  It is used
when Capiche is automatically selecting the range of material
widths and spacings to simulate.

	magiclayers['<layer_name>'] = '<paint_type>'

This variable is used to map names used in Capiche to layer names
used in magic.


## Lower level routines:

imported and called from `compute_coefficients.py`

- `build_fc_files_w1(stackupfile, metallist, condlist, widths, outfile, tolerance, verbose=0)`

	       stackupfile = name of the script file with the metal
			stack definition
	       metallist = list of metals to test as wires
	       condlist = list of conductors/substrates to test
	       widths = list with wire widths to test
	       outfile = name of output file with results
	       tolerance = initial tolerance to use for FasterCap
	       verbose = diagnostic output level

	    Output:  A file (or printed output) with entries:

		<metal> <cond> <width> <Ccoup>

		    where <width> is the metal wire width in microns and
		    <Ccoup> is the coupling between <metal> and <cond> in uF.

	    Description:  This routine generates an input file for
		FasterCap representing the 2D cross-section of a single
		metal wire over a conducting plane, where the conducting
		plane may be another metal or a substrate type.  FasterCap
		calculates the total coupling capacitance (per unit length)
		between the wire and the conductor/substrate.  This routine
		is used to find the maximum fringe capacitance per unit
		length (by substracting the area capacitance from the result
		and dividing by 2)
	
- `build_fc_files_w1n(stackupfile, metallist, condlist, widths, outfile, tolerance, verbose=0)`

	       stackupfile = name of the script file with the metal
	               stack definition
	       metallist = list of metals to test as wires
	       condlist = list of conductors/substrates to test
	       widths = list with wire widths to test
	       outfile = name of output file with results
	       tolerance = initial tolerance to use for FasterCap
	       verbose = diagnostic output level

	    Output:  A file (or printed output) with entries:

		<metal> <cond> <width> <Ccoup>

		    where <width> is the metal wire width in microns and
		    <Ccoup> is the coupling between <metal> and <cond> in uF.
	
	    Description:  This routine generates an input file for
		FasterCap representing the 2D cross-section of a single
		metal wire under a conducting plane, where the conducting
		plane is another metal higher than the first.  FasterCap
		calculates the total coupling capacitance (per unit length)
		between the wire and the conductor above.
	
- `build_fc_files_w1sh(stackupfile, metallist, condlist, subname, widths,	seps, outfile, tolerance, verbose=0)`

	       stackupfile = name of the script file with the metal
	               stack definition
	       metallist = list of metals to test as wires
	       condlist = list of conductors/substrates to test as shields
	       subname = name of the substrate type to use
	       widths = list with wire widths to test
	       seps = list with wire-to-shield separations to test
	       outfile = name of output file with results
	       tolerance = initial tolerance to use for FasterCap
	       verbose = diagnostic output level

	    Output:  A file (or printed output) with entries:

		<metal> <cond> <width> <sep> <Cmsub> <Ccsub> <Ccoup>

		    where <width> is the metal wire width in microns, <sep>
		    is the distance from the wire center to the edge of the
		    conductor underneath, <Cmsub> is the coupling from
		    <metal> to substrate, in uF;  <Ccsub> is the coupling
		    from <cond> to substrate, in uF; and <Ccoup> is the
		    coupling between <metal> and <cond> in uF.
	
	    Description:  This routine generates an input file for
		FasterCap representing the 2D cross-section of a single
		metal wire over a conducting shield wire, where the shield
		wire is another metal lower than the first, and where
		the left side of the shield wire extends far to the left
		(placed at -40um), and the right side of the shield wire
		terminates at a given distance from the wire center, with
		negative values representing increasing overlap to the
		right, and positive values representing increasing spacing
		to the left (note that the sign of the separation is the
		negative of the edge position on the X axis).  FasterCap
		calculates the total coupling capacitance (per unit length)
		between the wire and the shield below.  This routine is
		used to determine how much of the total fringe capacitance
		of a wire is incident upon a wire underneath, depending on
		how far the wire underneath extends into the fringing
		field.

- `build_fc_files_w2(stackupfile, metallist, condlist, widths, seps, outfile, tolerance, verbose=0)`

	       stackupfile = name of the script file with the metal
	               stack definition
	       metallist = list of metals to test as wires
	       condlist = list of conductors/substrates to test as shields
	       widths = list with wire widths to test
	       seps = list with wire-to-shield separations to test
	       outfile = name of output file with results
	       tolerance = initial tolerance to use for FasterCap
	       verbose = diagnostic output level

	    Output:  A file (or printed output) with entries:

		<metal> <cond> <width> <sep> <Cmsub> <Ccoup>

		    where <width> is the metal wire width in microns, <sep>
		    is the spacing between the two wires; <Cmsub> is the
		    coupling from <metal> (either wire) to <cond>, in uF;
		    and <Ccoup> is the coupling between the wires, in uF.
	
	    Description:  This routine generates an input file for
		FasterCap representing the 2D cross-section of two
		parallel wires of a given width and separation, over a
		conducting shield plane.  FasterCap calculates the total
		coupling capacitance (per unit length) between the two
		wires and, between one of the wires and the shield below.
		This routine is used to determine sidewall capacitance
		between neighboring wires on the same plane, and to
		determine the shielding effect of a neighboring wire on
		the amount of fringe capacitance to a conductor below.

- `build_fc_files_w2o(stackupfile, metal1list, metal2list, widths1, widths2, seps, outfile, tolerance, verbose=0)`

	       stackupfile = name of the script file with the metal
	               stack definition
	       metal1list = 1st list of metals to test as wires
	       metal2list = 2nd list of metals to test as wires
	       widths1 = list with 1st metal wire widths to test
	       widths2 = list with 2nd metal wire widths to test
	       seps = list with wire1-to-wire2 separations to test
	       outfile = name of output file with results
	       tolerance = initial tolerance to use for FasterCap
	       verbose = diagnostic output level

	    Output:  A file (or printed output) with entries:

		<metal1> <metal2> <width1> <width2> <sep> <Cm1sub> <Cm2sub> <Ccoup>

		    where <width1> is the wire width of <metal1> in microns,
		    <width2> is the wire width of <metal2> in microns, <sep>
		    is the lateral spacing between the two wires; <Cm1sub> is
		    the coupling from <metal1> to substrate, in uF; <Cm2sub>
		    is the coupling from <metal2> to substrate, in uF; and
		    <Ccoup> is the coupling between <metal1> and <metal2>, in uF.
	
	    Description:  This routine generates an input file for
		FasterCap representing the 2D cross-section of two
		wires of different metal types, each with a given
		width, and with edges separated by the given lateral
		separation distance.  FasterCap calculates the coupling
		capacitance between the wires and the coupling from each
		wire to the substrate.  It is used to validate parasitic
		capacitance modeling for any geometry of two wires.

- `build_mag_files_w1(stackupfile, startupscript, metallist, condlist, widths, outfile, verbose=0)`

	       stackupfile = name of the script file with the metal
	               stack definition
	       startupscript = name of the magic startup script
	       metallist = list of metals to test as wires
	       condlist = list of conductors/substrates to test
	       widths = list with wire widths to test
	       outfile = name of output file with results
	       verbose = diagnostic output level

	    Output:  A file (or printed output) with entries:

		<metal> <cond> <width> <Ccoup>

		    where <width> is the metal wire width in microns and
		    <Ccoup> is the coupling between <metal> and <cond> in uF.

	    Description:  This file corresponds to build_fc_files_w1() and
		build_fc_files_w1n(), but uses magic to construct a layout
		of the given geometry and extract the parasitics using
		magic's extraction models for the process.  Instead of a
		2D model, the geometry is formed from very long wires and
		the result is divided by the wire length.  There is not a
		separate routine for conducting planes over vs. under the
		metal wire, since for layout there is no fundamental
		difference between drawing a layer that is above the metal wire
		vs. drawing a layer that is below the metal wire.

- `build_mag_files_w1sh(stackupfile, startupscript, metallist, condlist, subname, widths, seps, outfile, verbose=0)`

	       stackupfile = name of the script file with the metal
	               stack definition
	       startupscript = name of the magic startup script
	       metallist = list of metals to test as wires
	       condlist = list of conductors/substrates to test
	       subname = name of the substrate layer to use
	       widths = list with wire widths to test
	       seps = list with wire-to-shield separations to test
	       outfile = name of output file with results
	       verbose = diagnostic output level

	    Output:  A file (or printed output) with entries:

		<metal> <cond> <width> <sep> <Cmsub> <Ccsub> <Ccoup>

		    where <width> is the metal wire width in microns, <sep>
		    is the distance from the wire center to the edge of the
		    conductor underneath, <Cmsub> is the coupling from
		    <metal> to substrate, in uF;  <Ccsub> is the coupling
		    from <cond> to substrate, in uF; and <Ccoup> is the
		    coupling between <metal> and <cond> in uF.
	
	    Description:  This file corresponds to build_fc_files_w1sh(),
		but uses magic to construct a layout of the given geometry
		and extract the parasitics using magic's extraction models
		for the process.  Instead of a 2D model, the geometry is
		formed from very long wires and the result is divided by
		the wire length.

- `build_mag_files_w2(stackupfile, startupscript, metallist, condlist, widths, seps, outfile, verbose=0)`

	       stackupfile = name of the script file with the metal
	               stack definition
	       startupscript = name of the magic startup script
	       metallist = list of metals to test as wires
	       condlist = list of conductors/substrates to test
	       widths = list with wire widths to test
	       seps = list with wire-to-shield separations to test
	       outfile = name of output file with results
	       verbose = diagnostic output level

	    Output:  A file (or printed output) with entries:

		<metal> <cond> <width> <sep> <Cmsub> <Ccoup>

		    where <width> is the metal wire width in microns, <sep>
		    is the spacing between the two wires; <Cmsub> is the
		    coupling from <metal> (either wire) to <cond>, in uF;
		    and <Ccoup> is the coupling between the wires, in uF.
	
	    Description:  This file corresponds to build_fc_files_w2(),
		but uses magic to construct a layout of the given geometry
		and extract the parasitics using magic's extraction models
		for the process.  Instead of a 2D model, the geometry is
		formed from very long wires and the result is divided by
		the wire length.

## Lower level routines called as applications:

- `build_fc_files_w1.py <stack_def_file> [options]`

	    Where:
		<stack_def_file> is the python script with the metal stack definition.
	    And where [options] may be one or more of:
		-metals=<metal>[,...]  (restrict wire type to one or more metals)
		-conductors=<conductor>[,...] (restrict conductor type to one or
						more types)
		-width=<start>,<stop>,<step> (wire width range, in microns)
		-tol[erance]=<value>         (FasterCap tolerance)
		-file=<name>                 (output filename for results)
		-verbose=<level>	     (level of diagnostic output)

	    Output:  See explanation of the build_fc_files_w1() routine above.
	    Description:  See explanation of build_fc_files_w1() routine above.

- `build_fc_files_w1n.py <stack_def_file> [options]`

	    Where:
		<stack_def_file> is the python script with the metal stack definition.
	    And where [options] may be one or more of:
		-metals=<metal>[,...]    (restrict wire type to one or more metals)
		-shields=<metal>[,...]   (restrict shield type to one or more metals)
		-sub[strate]=<substrate> (substrate type)
		-width=<start>,<stop>,<step> (wire width range, in microns)
		-tol[erance]=<value>         (FasterCap tolerance)
		-file=<name>                 (output filename for results)
		-verbose=<level>	     (level of diagnostic output)

	    Output:  See explanation of the build_fc_files_w1n() routine above.
	    Description:  See explanation of build_fc_files_w1n() routine above.

- `build_fc_files_w1sh.py <stack_def_file> [options]`

	    Where:
		<stack_def_file> is the python script with the metal stack definition.
	    And where [options] may be one or more of:
		-metals=<metal>[,...]  (restrict wire type to one or more metals)
		-shields=<metal>[,...] (restrict shield type to one or more metals)
		-sub[strate]=<substrate>     (substrate type)
		-width=<start>,<stop>,<step> (wire width range, in microns)
		-sep=<start>,<stop>,<step>   (separation range, in microns)
		-tol[erance]=<value>         (FasterCap tolerance)
		-file=<name>                 (output filename for results)
		-verbose=<level>	     (level of diagnostic output)

	    Output:  See explanation of the build_fc_files_w1sh() routine above.
	    Description:  See explanation of build_fc_files_w1sh() routine above.

- `build_fc_files_w2.py <stack_def_file> [options]`

	    Where:
		<stack_def_file> is the python script with the metal stack definition.
	    And where [options] may be one or more of:
		-metals=<metal>[,...]  (restrict wire type to one or more metals)
		-sub[strate]=<substrate>[,...] (restrict substrate type)
		-width=<start>,<stop>,<step> (wire width range, in microns)
		-sep=<start>,<stop>,<step>   (separation range, in microns)
		-tol[erance]=<value>         (FasterCap tolerance)
		-file=<name>                 (output filename for results)
		-verbose=<level>	     (level of diagnostic output)

	    Output:  See explanation of the build_fc_files_w2() routine above.
	    Description:  See explanation of build_fc_files_w2() routine above.

- `build_fc_files_w2o.py <stack_def_file> [options]`

	    Where:
		<stack_def_file> is the python script with the metal stack definition.
	    And where [options] may be one or more of:
		-metal1=<metal>[,...] (restrict 1st wire type to one or more metals)
		-metal2=<metal>[,...] (restrict 2nd wire type to one or more metals)
		-sub[strate]=<substrate>      (substrate type)
		-width1=<start>,<stop>,<step> (1st wire width range, in microns)
		-width2=<start>,<stop>,<step> (2nd wire width range, in microns)
		-sep=<start>,<stop>,<step>    (separation range, in microns)
		-tol[erance]=<value>          (FasterCap tolerance)
		-file=<name>                  (output filename for results)
		-verbose=<level>	     (level of diagnostic output)

	    Output:  See explanation of the build_fc_files_w2o() routine above.
	    Description:  See explanation of build_fc_files_w2o() routine above.

- `build_mag_files_w1.py <stack_def_file> <magic_startup_script> [options]`

	    Where:
		<stack_def_file> is the python script with the metal stack definition.
		<magic_startup_script> is the .magicrc file for the technology
	    And where [options] may be one or more of:
		-metals=<metal>[,...]  (restrict wire type to one or more metals)
		-conductors=<conductor>[,...] (restrict conductor type to one or
						more types)
		-width=<start>,<stop>,<step> (wire width range, in microns)
		-file=<name>                 (output filename for results)
		-verbose=<level>	     (level of diagnostic output)

	    Output:  See explanation of the build_mag_files_w1() routine above.
	    Description:  See explanation of build_mag_files_w1() routine above.

- `build_mag_files_w1sh.py <stack_def_file> <magic_startup_script> [options]`

	    Where:
		<stack_def_file> is the python script with the metal stack definition.
		<magic_startup_script> is the .magicrc file for the technology
	    And where [options] may be one or more of:
		-metals=<metal>[,...]  (restrict wire type to one or more metals)
		-shields=<metal>[,...]  (restrict shield type to one or more metals)
		-sub[strate]=<substrate>[,...] (restrict substrate type)
		-width=<start>,<stop>,<step> (wire width range, in microns)
		-sep=<start>,<stop>,<step>   (separation range, in microns)
		-file=<name>                 (output filename for results)
		-verbose=<level>	     (level of diagnostic output)

	    Output:  See explanation of the build_mag_files_w1sh() routine above.
	    Description:  See explanation of build_mag_files_w1sh() routine above.

- `build_mag_files_w2.py <stack_def_file> <magic_startup_script> [options]`

	    Where:
		<stack_def_file> is the python script with the metal stack definition.
		<magic_startup_script> is the .magicrc file for the technology
	    And where [options] may be one or more of:
		-metals=<metal>[,...]  (restrict wire type to one or more metals)
		-sub[strate]=<substrate>[,...] (restrict substrate type)
		-width=<start>,<stop>,<step> (wire width range, in microns)
		-sep=<start>,<stop>,<step>   (separation range, in microns)
		-file=<name>                 (output filename for results)
		-verbose=<level>	     (level of diagnostic output)
	
	    Output:  See explanation of the build_mag_files_w2() routine above.
	    Description:  See explanation of build_mag_files_w2() routine above.

# Work to do:

Capiche is a work in progress.

1. Put new analytic expressions into magic (tanh, arctan models)
2. Add command in magic to change the halo for parasitic capacitances
    on the command-line.
3. Evaluate and refine models in magic, especially for change in
    capacitance vs. wire width (which is currently ignored by
    magic completely;  need to understand the error bound of this
    approximation).
4. Add analysis of coupling across a shield wire to a wire on the
    other side (another thing that magic ignores).
5. Refine sidewall coupling model to include variation with height
    above substrate or shield plane.
6. Add metal stackup for GF180MCU.
7. Add a script to create a drawing of each geometry example for
    reference.
