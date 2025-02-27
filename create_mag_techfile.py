# TODO

import os
import sys
import numpy
import subprocess

def create_mag_techfile(stackupfile, metals, substrates, areacap, fringe, sidewall, fringeshield, fringepartial, verbose=0):
    """
    """

    #--------------------------------------------------------------
    # Obtain the metal stack.  The metal stack file is in the
    # format of executable python, so use exec().
    #--------------------------------------------------------------

    try:
        locals = {}
        exec(open(stackupfile, 'r').read(), None, locals)
    except:
        print('Error:  No metal stack file ' + stackupfile + '!')
        return 1

    try:
        process = locals['process']
    except:
        print('Warning:  Metal stack does not define process!')
        process = 'unknown'

    try:
        layers = locals['layers']
    except:
        print('Error:  Metal stack does not define layers!')
        return 1

    try:
        limits = locals['limits']
    except:
        print('Error:  Metal stack does not define limits!')
        return 1

    try:
        magiclayers = locals['magiclayers']
    except:
        print('Error:  Metal stack does not define magiclayers!')
        return 1

    try:
        magicextractstyle = locals['magicextractstyle']
    except:
        # Use default
        magicextractstyle = None

    try:
        magicplanes = locals['magicplanes']
    except:
        print('Error:  Metal stack does not define magicplanes!')
        return 1

    try:
        magicaliases = locals['magicaliases']
    except:
        print('Error:  Metal stack does not define magicaliases!')
        return 1

    try:
        magicstyles = locals['magicstyles']
    except:
        print('Error:  Metal stack does not define magicstyles!')
        return 1

    # Get the unique list of planes, but keep the order
    seen = set()
    unique_planes = [plane for plane in magicplanes.values() if not (plane in seen or seen.add(plane))]

    # Get the name for the substrate
    # This is the first layer in the stackup
    substrate_name = substrates[0]

    print(metals)
    print(substrates)
    print(areacap)
    print(fringe)
    print(sidewall)
    print(fringeshield)
    print(fringepartial)

    """
    TODO: how to handle ndiff,mvndiff->allactivenonfet?
    merge layers with same alias and only use first entry?
    but ndiff,mvndiff have different results...
    
    TODO: deep nwell
    
    """

    ext_data = ''
    for metal in metals:
        
        layer = magiclayers[metal]
        plane = magicplanes[metal]
        alias = magicaliases[metal]
        
        layer_or_alias = alias if alias != None else layer
        
        print(layer)
        print(plane)
        print(alias)
        
        ext_data += f"""# {metal}
 defaultsidewall    {layer_or_alias} {plane} {sidewall[metal][0]:.3f} {sidewall[metal][1]:.3f}
 defaultareacap     {layer_or_alias} {plane} {areacap[metal+'+'+substrate_name]:.3f}
 defaultperimeter   {layer_or_alias} {plane} {fringe[metal+'+'+substrate_name]:.3f}\n\n"""

        for substrate in substrates:
            # Ignore transistor gates
            if 'diff' in substrate and 'poly' in metal:
                continue
            print(substrate)
            
            subs_layer = magiclayers[substrate]
            subs_plane = magicplanes[substrate]
            subs_alias = magicaliases[substrate]
            
            subs_layer_or_alias = subs_alias if subs_alias != None else subs_layer
            
            print(subs_layer)
            print(subs_plane)
            print(subs_alias)

            ext_data += f"""# {metal}->{substrate}
 defaultoverlap     {layer_or_alias} {plane} {subs_layer_or_alias} {subs_plane}  {areacap[metal+'+'+substrate]:.3f}
 defaultsideoverlap {layer_or_alias} {plane} {subs_layer_or_alias} {subs_plane}  {fringe[metal+'+'+substrate]:.3f}\n\n"""

        for other_metal in metals:
            # Ignore everything above and myself
            if metals.index(other_metal) >= metals.index(metal):
                continue
        
            print(substrate)
            
            met_layer = magiclayers[other_metal]
            met_plane = magicplanes[other_metal]
            met_alias = magicaliases[other_metal]
            
            met_layer_or_alias = met_alias if met_alias != None else met_layer
            
            print(met_layer)
            print(met_plane)
            print(met_alias)

            ext_data += f"""# {metal}->{other_metal}
 defaultoverlap     {layer_or_alias} {plane} {met_layer_or_alias} {met_plane} {areacap[metal+'+'+other_metal]:.3f}
 defaultsideoverlap {layer_or_alias} {plane} {met_layer_or_alias} {met_plane} {fringe[metal+'+'+other_metal]:.3f}
 defaultsideoverlap {met_layer_or_alias} {met_plane} {layer_or_alias} {plane} {fringe[other_metal+'+'+metal]:.3f}\n\n"""



    print(ext_data)

    # TODO generate magic tech file
    if True:
        with open(os.path.join(process, 'magic', f'{process}.tech'), 'w') as magictech_file:
            magictech_file.write(f"""tech
  format 35
  {process}
end

version
  version 0.0
  description "Dummy technology file generated by capiche"
end

planes
{'\n'.join(['  ' + plane for plane in unique_planes])}
end

types
{'\n'.join(['  ' + plane + ' ' + magiclayers[layer] for layer, plane in magicplanes.items()])}
end

contact
end

aliases
{'\n'.join(['  ' + alias + ' ' + magiclayers[layer] for layer, alias in magicaliases.items() if alias != None])}
end

styles
 styletype mos
{'\n'.join(['  ' + magiclayers[layer] + ' ' + style for layer, style in magicstyles.items()])}
end

compose
end

connect
end

cifoutput
 style gdsii
 scalefactor 10  nanometers
 gridlimit 5
end

cifinput
end

# mzrouter
# end

drc
end

extract
 style ngspice variants ()
 cscale 1

 variants *
 lambda 1.0

 units	microns
 step   7
 sidehalo 8
 fringeshieldhalo 8

{'\n'.join([' planeorder ' + plane + ' ' + str(i) for i, plane in enumerate(unique_planes)])}

variants ()
# Nominal capacitances

# Note: This section was auto-generated by capiche

{ext_data}
end

# wiring
# end

# router
# end

# plowing
# end

# plot
# end 
""")
