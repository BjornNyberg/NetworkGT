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

arcpy.env.overwriteOutput = True

def main (infc,field,dangle,short,trim,extend,join,loops,output,output2):
    try:
	field = field.split(';')
	if field[0] == '':
            field = field[0]
	arcpy.FeatureToLine_management([infc],"in_memory\\templines")

        arcpy.RepairGeometry_management("in_memory\\templines")
	
	d = dangle.split(" ")

	if eval(d[0]) > 0:

            if trim == 'true':
	        arcpy.AddMessage('Triming fracture networks by dangle length')
	        arcpy.TrimLine_edit("in_memory\\templines", dangle, "KEEP_SHORT")

	    if join == 'true':
                
		nodes = {}
	        arcpy.AddMessage('Merging offset fracture networks within dangle length')
	        
	        arcpy.FeatureVerticesToPoints_management("in_memory\\templines", "in_memory\\temppoints", "BOTH_ENDS")

	        curfields = [f.name.lower() for f in arcpy.ListFields("in_memory\\temppoints")]

                if 'x' not in curfields:
                   arcpy.AddField_management("in_memory\\temppoints",'x',"DOUBLE")

                if 'y' not in curfields:
                    arcpy.AddField_management("in_memory\\temppoints",'y',"DOUBLE")


    	        arcpy.CalculateField_management("in_memory\\temppoints",'x',"!SHAPE.CENTROID.X!","PYTHON_9.3")
	        arcpy.CalculateField_management("in_memory\\temppoints",'y',"!SHAPE.CENTROID.y!","PYTHON_9.3")	

                with arcpy.da.SearchCursor("in_memory\\temppoints",['x','y']) as cursor:
                    for row in cursor:
                        try:
                            ID = (row[0],row[1]) 
                            if ID in nodes:
                                value = nodes[ID]
                                value += 1
                                nodes[ID] = value
                            else:
                                nodes[ID] = 1

                        except Exception,e:
                            arcpy.AddError('%s'%(e))
                            continue


            	with arcpy.da.UpdateCursor("in_memory\\temppoints",['x','y']) as cursor:
                    for row in cursor:
			ID = (row[0],row[1]) 
			value = nodes[ID]
			if value > 1:
			    cursor.deleteRow()		    
		del nodes	
		
			
	        arcpy.GenerateNearTable_analysis("in_memory\\temppoints", "in_memory\\temppoints", "in_memory\\temptable", dangle,"LOCATION","","", "")

		Connections = {}
                with arcpy.da.SearchCursor("in_memory\\temptable",['FROM_X','FROM_Y','NEAR_X','NEAR_Y']) as cursor:
                    for row in cursor:
                        try:
                            Connections[(row[0],row[1])] = (row[2],row[3])

                        except Exception,e:
                            arcpy.AddError('%s'%(e))
                            continue

		array = arcpy.Array()
                if Connections:
                    Count = 0 
                    with arcpy.da.UpdateCursor("in_memory\\templines",['SHAPE@']) as cursor:
                        for row in cursor:
                            start = row[0].firstPoint
                            end = row[0].lastPoint
                            branch = (start.X,start.Y)
                            rbranch = (end.X,end.Y)

                            if branch in Connections:
                               Count += 1
                               addgeom = Connections[branch]                             
                               array.add(arcpy.Point(addgeom[0],addgeom[1]))
                               for part in row[0]:
                                   for pnt in part:
                                       point = (pnt.X,pnt.Y)                                
                                       array.add(arcpy.Point(point[0],point[1]))
                               geom = arcpy.Polyline(array)
                               array.removeAll()
                               row[0] = geom
                               cursor.updateRow(row)
                               if addgeom in Connections:
                                   del Connections[addgeom]

                            elif rbranch in Connections:
                               Count += 1
                               addgeom = Connections[rbranch]
                               for part in row[0]:
                                   for pnt in part:
                                       point = (pnt.X,pnt.Y)                                
                                       array.add(arcpy.Point(point[0],point[1]))                          
                               array.add(arcpy.Point(addgeom[0],addgeom[1]))
                               geom = arcpy.Polyline(array)
                               array.removeAll()
                               row[0] = geom
                               cursor.updateRow(row)
                               if addgeom in Connections:
                                   del Connections[addgeom]
                    if Count > 0:
                       arcpy.AddWarning('Joined %s features'%(Count))

	    if extend == 'true':
	        arcpy.AddMessage('Extending fracture networks by dangle length')
	        arcpy.ExtendLine_edit("in_memory\\templines", dangle, "FEATURE")


	    if short == 'true':
	        arcpy.AddMessage('Removing short fracture networks by dangle length')

		Graph = {} #Store all node connections
            
                with arcpy.da.SearchCursor("in_memory\\templines",['SHAPE@']) as cursor:
		    
                    for row in cursor:
                        try:
                            start = row[0].firstPoint
                            end = row[0].lastPoint
                            branch = [(round(start.X,4),round(start.Y,4)),(round(end.X,4),round(end.Y,4))]

                            for b in branch:
                                if b in Graph: #node count
                                    Graph[b] += 1
                                else:
                                    Graph[b] = 1
                            
                        except Exception,e:
                            arcpy.AddError('%s'%(e))
                            continue
                Count = 0
                with arcpy.da.UpdateCursor("in_memory\\templines",['SHAPE@']) as cursor:
                    for row in cursor:
                        Length = row[0].getLength('PLANAR',d[1])
			
	
                        start = row[0].firstPoint
                        end = row[0].lastPoint
                        branch = [(round(start.X,4),round(start.Y,4)),(round(end.X,4),round(end.Y,4))]
                        C = 0
                        for b in branch:
                            value = Graph[b] 
                            C += value
                        if C == 2 and float(d[0]) > Length:
			    Count += 1
                            cursor.deleteRow()
		if Count > 0:
                    arcpy.AddWarning('Deleted %s short features'%(Count))

        if loops == 'true':
	    Count = 0  
            with arcpy.da.UpdateCursor("in_memory\\templines",['shape@']) as cursor:  	           
                for row in cursor:

                    start = row[0].firstPoint
                    end = row[0].lastPoint
                    branch = [(round(start.X,4),round(start.Y,4)),(round(end.X,4),round(end.Y,4))]
                    if branch[0] == branch[1]:
                        cursor.deleteRow()
			Count += 1
	    if Count > 0:
                arcpy.AddWarning('Deleted %s loops'%(Count))
            del cursor,row
            
        arcpy.AddMessage('Creating output files')
        arcpy.Dissolve_management("in_memory\\templines",output,field,"","SINGLE_PART", "DISSOLVE_LINES")   #remove overlaps and dissolve based on specified fields
	
	if output2:
	    arcpy.SymDiff_analysis(output, infc, output2, "ONLY_FID")

    except Exception,e:
        arcpy.AddError('%s'%(e))

    finally:
	del_files = ["in_memory\\templines","in_memory\\temptable"]
        
        for fname in del_files:
            try:
                arcpy.DeleteFeatures_management(fname)
            except Exception,e:
                continue
            
if __name__ == "__main__":        
    ###Inputs###
        
    infc = arcpy.GetParameterAsText(0)
    field = arcpy.GetParameterAsText(1)
    dangle = arcpy.GetParameterAsText(2)
    output = arcpy.GetParameterAsText(3)
    output2 = arcpy.GetParameterAsText(4)
    short = arcpy.GetParameterAsText(5)
    trim = arcpy.GetParameterAsText(6)
    extend = arcpy.GetParameterAsText(7)
    join = arcpy.GetParameterAsText(8)
    loops = arcpy.GetParameterAsText(9)
  
    main(infc,field,dangle,short,trim,extend,join,loops,output,output2)
