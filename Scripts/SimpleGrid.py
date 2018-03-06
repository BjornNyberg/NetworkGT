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

def main (infc,Width,outfc,radius):

    if 'shp' in outfc:
	arcpy.AddError('Output parameter must be saved in a geodatabase')
	sys.exit()


    extent = arcpy.Describe(infc).extent
    orig = "%s %s"%(extent.XMin,extent.YMin)
    add = extent.YMin*0.00001
    yaxis = "%s %s"%(extent.XMin,extent.YMin+add)
    
    arcpy.CreateFishnet_management("in_memory\\fishnet",orig,yaxis, Width, Width, "", "", "" ,"", infc, "POLYGON")

    arcpy.MakeFeatureLayer_management("in_memory\\fishnet", "in_memory\\layer")
    arcpy.SelectLayerByLocation_management("in_memory\\layer", "COMPLETELY_WITHIN", infc)
    arcpy.CopyFeatures_management("in_memory\\layer", outfc)

    if radius:
	
    	fields = ['Area','Circumfere']
	arcpy.AddField_management(outfc, 'Area',"DOUBLE")
	arcpy.AddField_management(outfc, 'Circumfere',"DOUBLE","","","","Circumference")

        arcpy.AddField_management(outfc, 'S_Radius',"TEXT")
	arcpy.FeatureToPoint_management(outfc, "in_memory\\fishnet_points")
    	arcpy.Buffer_analysis("in_memory\\fishnet_points","in_memory\\buffer",radius, "FULL", "ROUND")

	radius_v = radius.split(' ')
	
	data = {}

	cursorm = [m_data for m_data in arcpy.da.SearchCursor(infc,['SHAPE@'])]
	
	count = arcpy.GetCount_management("in_memory\\buffer").getOutput(0)
        arcpy.SetProgressor("step", "Reading Buffer Parameters",0,eval(count),1)

	R1 = 1

        with arcpy.da.SearchCursor("in_memory\\buffer",['OID@','SHAPE@']) as cursor:
            for row in cursor:
                for m in cursorm:
                    inter = row[1].intersect(m[0],4)
                    if inter.length != 0.0:
                        data[row[0]]=(inter.getLength('PLANAR',radius_v[1]),inter.getArea('PLANAR',radius_v[1]))
                        break
                arcpy.SetProgressorPosition()

        with arcpy.da.SearchCursor(outfc,['OID@']) as cursor:
            for row in cursor:
		if row[0] < R1:
		    R1 = row[0]
		
	fields.extend(['S_Radius','OID@'])

	with arcpy.da.UpdateCursor(outfc,fields) as cursor:
	    for row in cursor:
	        values = data[row[-1]+(1-R1)]
	        row[0] = values[1]
		row[1] = values[0]
		row[2] = radius	
		cursor.updateRow(row)   	


if __name__ == "__main__":        
    ###Inputs###
        
    infc = arcpy.GetParameterAsText(0)
    D = arcpy.GetParameterAsText(1)
    radius = arcpy.GetParameterAsText(2)
    outfc = arcpy.GetParameterAsText(3)

    main(infc,D,outfc,radius)

