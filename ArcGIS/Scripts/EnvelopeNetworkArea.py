#==================================
#Author Bjorn Burr Nyberg 
#University of Bergen
#Contact bjorn.nyberg@uib.no
#Copyright 2016
#==================================

'''This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.'''


import  arcpy

def main (infc,outfc):
    try:

	if 'shp' in outfc:
	    arcpy.AddError('Output parameter must be saved in a geodatabase')
	    sys.exit()

        arcpy.Buffer_analysis(infc,"in_memory\\buffer",1, "FULL", "ROUND")
        arcpy.MinimumBoundingGeometry_management("in_memory\\buffer", outfc, "ENVELOPE", "ALL")
    except Exception,e:
        arcpy.AddError('%s'%(e))
        
    finally:
        del_files = ["in_memory\\buffer"]
        for fname in del_files:
            try:
                arcpy.DeleteFeatures_management(fname)
            except Exception:
                continue

if __name__ == "__main__":        
    ###Inputs###
        
    infc = arcpy.GetParameterAsText(0)
    outfc = arcpy.GetParameterAsText(1)

    main(infc,outfc)

