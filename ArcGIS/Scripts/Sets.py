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


import  os,arcpy,math

def main (infc,bins):

    bins = eval('['+ bins + ']')

    for bin in bins:
        if bin[0] > 180 or bin[1] > 180:
	    arcpy.AddError('Bins must range between 0 and 180')

    curfields = [f.name.lower() for f in arcpy.ListFields(infc)]


    if 'sets' not in curfields:
        arcpy.AddField_management(infc, 'Sets', "LONG")


    if 'orient' not in curfields:
	arcpy.AddField_management(infc, "Orient", "DOUBLE")


    with arcpy.da.UpdateCursor(infc, ['Shape@','Sets','Orient']) as cursor:

        for row in cursor:

            sx,sy = row[0].firstPoint.X,row[0].firstPoint.Y
            ex,ey = row[0].lastPoint.X,row[0].lastPoint.Y

            dx = ex - sx
            dy =  ey - sy

            angle = math.degrees(math.atan2(dy,dx))
            Bearing = (90.0 - angle) % 360

            if Bearing >= 180:
                Bearing -= 180

	    Value = -1

            for enum, bin in enumerate(bins):
		if bin[0] > bin[1]:
		    if Bearing > bin[0] or Bearing <= bin[1]:
        	        Value = enum
        	        break

                elif Bearing > bin[0] and Bearing <= bin[1]:
        	    Value = enum
        	    break

	    row[1] = Value
   	    row[2] = round(Bearing,2)

	    cursor.updateRow(row)


if __name__ == "__main__":
    ###Inputs###

    infc = arcpy.GetParameterAsText(0)
    bins = arcpy.GetParameterAsText(1)

    main(infc,bins)
