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

import arcpy, os, sys

def n_count(node_count):
    if node_count == 1:
        V = 'I'
    elif node_count == 3:
	V = 'Y'
    elif node_count == 4:
        V = 'X'
    else:
	V = 'Error'
	arcpy.AddWarning('Mismatching number of nodes found - %s' %(node_count))
    return V
                     
def main (infc,outfc,outfc2,mask,mask_outline,attributes):

    try:
	
        arcpy.AddMessage('Creating Output Files')
        del_files = ["in_memory\\templines"]
        
        unknown_nodes = []
        arcpy.FeatureToLine_management([infc],"in_memory\\templines")

        if mask_outline:
            del_files.extend(["in_memory\\points","in_memory\\network","in_memory\\points_sp"])
            arcpy.Intersect_analysis([mask_outline,"in_memory\\templines"], "in_memory\\network", "", "", "LINE")
            arcpy.Intersect_analysis([mask_outline,"in_memory\\templines"], "in_memory\\points", "", "", "POINT")
            arcpy.MultipartToSinglepart_management("in_memory\\points","in_memory\\points_sp")

            infc = "in_memory\\network"

            arcpy.AddMessage('Reading Unknown Nodes')
            for row in arcpy.da.SearchCursor("in_memory\\points_sp",['SHAPE@']):
                    unknown_nodes.append((round(row[0].firstPoint.X,4),round(row[0].firstPoint.Y,4)))
        else:
            infc = "in_memory\\templines"

        curfields = [f.name for f in arcpy.ListFields(mask)]

        if 'S_Radius' in curfields:
            del_files.extend(["in_memory\\points","in_memory\\fishnet_points","in_memory\\buffer"])
            arcpy.FeatureToPoint_management(mask, "in_memory\\fishnet_points")
            arcpy.Buffer_analysis("in_memory\\fishnet_points","in_memory\\buffer","S_Radius", "FULL", "ROUND")

            mask = "in_memory\\buffer"


        dname = os.path.dirname(outfc)
        dname2 = os.path.dirname(outfc2)

        arcpy.CreateFeatureclass_management(dname,os.path.basename(outfc),"POLYLINE",'','ENABLED','ENABLED',infc)

        arcpy.AddField_management(outfc, 'Class',"TEXT")
        arcpy.AddField_management(outfc, 'Connection',"TEXT")
        arcpy.AddField_management(outfc, 'B_Weight', "DOUBLE")
        arcpy.AddField_management(outfc, 'Sample_No_', "LONG","","","","Sample No.")

        arcpy.CreateFeatureclass_management(dname2,os.path.basename(outfc2),"POINT",'','ENABLED','ENABLED',infc)

        arcpy.AddField_management(outfc2, 'Class', "TEXT")
        arcpy.AddField_management(outfc2, 'Sample_No_', "LONG","","","","Sample No.")

        curfields = curfields = [f.name for f in arcpy.ListFields(outfc)]
        outfields =  [(f.name,f.type) for f in arcpy.ListFields(infc)]
        infields =  ['Shape@']
        fields= ['Class','Connection','B_Weight','Sample_No_','SHAPE@']

        if attributes == 'true':
            arcpy.AddMessage('Creating Fields')
            for fname,ftype in outfields:
                if ftype != 'OID' and fname != 'Shape':
                    if fname not in curfields:
                        if ftype != 'OID':
                            arcpy.AddField_management(outfc,fname,ftype)
                    fields.append(fname)
                    infields.append(fname)

            
        Graph = {} #Store all node connections
        
        arcpy.AddMessage('Reading End Nodes')

        with arcpy.da.SearchCursor(infc,['SHAPE@']) as cursor:
 
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

        
        arcpy.AddMessage('Creating Branches')
        c_points = {}
        point_data = []
        
        with arcpy.da.SearchCursor(mask,['SHAPE@','OID@']) as cursor:
            cursorm = [m_data for m_data in cursor]

        count = arcpy.GetCount_management(infc).getOutput(0)
        arcpy.SetProgressor("step", "Creating Branches",0,eval(count),1)    
        with arcpy.da.InsertCursor(outfc,fields) as cursor:
            with arcpy.da.SearchCursor(infc,infields) as cursor2:
                for row in cursor2:
                    try:      
                        start = row[0].firstPoint
                        end = row[0].lastPoint
                        branch = [(round(start.X,4),round(start.Y,4)),(round(end.X,4),round(end.Y,4))]
                        name = []
                        
                        for (x,y) in branch:
                            
                            if (x,y) in unknown_nodes:
                                V = 'U'
                            else:
                                if (x,y) in Graph:
				    node_count = Graph[(x,y)]
                                    V = n_count(node_count)
				else:
				    V = 'Error'
                                    arcpy.AddWarning('Error found at node %s %s'%(x,y))
                            name.append(V)

                        Class = " - ".join(sorted(name[:2])) #Organize the order of names
                        name = Class.replace('X','C').replace('Y','C')
                        name = name.split(" - ")
                        Connection = " - ".join(sorted(name))
                            
                        for m in cursorm:
                            
                            if row[0].within(m[0]): #Branches

                                weight = 1
      
                                for (x,y) in branch:  #Points
                                    testPoint = arcpy.Point(x,y)
       
                                    if not testPoint.within(m[0].buffer(-0.0001)): #Test if point is on edge of sample area
                                        V = 'E'
                                        weight -= 0.5

                                    elif (x,y) in unknown_nodes:
                                        V = 'U'
                                        weight -= 0.5

                                    else:
                      		        if (x,y) in Graph:
                                            node_count = Graph[(x,y)]
                                            V = n_count(node_count)
			                else:
				            V = 'Error'	
					    arcpy.AddWarning('Error found at node %s %s'%(x,y))

                                    if m[1] in c_points:
                                        if (x,y) not in c_points[m[1]]:
                                            data2 = [V,m[1],(x,y)]
                                            
                                            c_points[m[1]].append((x,y))
                                            point_data.append(data2)
                                    else:
                                        data2 = [V,m[1],(x,y)]
                                        c_points[m[1]]=[(x,y)]
                                        point_data.append(data2)


                     
                                data = [Class,Connection,weight,m[1],row[0]]
                
                                for enum,v in enumerate(infields[1:]):
                                    data.append(row[enum+1])
                                
                                cursor.insertRow(data)
                                    
                            else:
                                
                                geom = m[0].intersect(row[0],2)
                                for part in geom: #Check for multipart polyline

                                    inter = arcpy.Polyline(part) #intersected geometry
                                    if inter.length != 0.0: #Branches

                                        start = inter.firstPoint
                                        end = inter.lastPoint
                                        inter_branch = [(start.X,start.Y),(end.X,end.Y)]

                                        weight = 1
                
                                        for (x,y) in inter_branch: #Points
                                            rx,ry = round(x,4),round(y,4)   
               
                                            V = 'E'
                                                
                                            testPoint = arcpy.Point(x,y)

                                            if testPoint.within(m[0]):

                                                if (rx,ry) in unknown_nodes:
                                                    V = 'U'
                                                else:
                                  		    if (rx,ry) in Graph:
                                                        node_count = Graph[(rx,ry)]
                                                        V = n_count(node_count)
						    else:
				       		        V = 'Error'	
							arcpy.AddWarning('Error found at node %s %s'%(rx,ry))
                       

                                            if m[1] in c_points:
                                                if (rx,ry) not in c_points[m[1]]:
                                                    data2 = [V,m[1],(x,y)]
                                                    c_points[m[1]].append((rx,ry))
                                                    point_data.append(data2)
                                            else:
                                                c_points[m[1]]=[(rx,ry)]
                                                data2 = [V,m[1],(x,y)]
                                                point_data.append(data2)

                                            if V == 'E' or V == 'U':
                                                weight -= 0.5

                                        data = [Class,Connection,weight,m[1],inter]
                                            
                                        for enum,v in enumerate(infields[1:]):
                                            data.append(row[enum+1])

                                        cursor.insertRow(data)
                               
                        arcpy.SetProgressorPosition()
                        
                    except Exception,e:
                        arcpy.AddError('%s'%(e))
                        continue 
        del cursorm

        fields2= ['Class','Sample_No_','SHAPE@']
        arcpy.AddMessage('Creating Nodes')
        
	arcpy.SetProgressor("step", "Creating Nodes",0,len(point_data),1)  
        with arcpy.da.InsertCursor(outfc2,fields2) as cursor2:  
            for data2 in point_data:  
                cursor2.insertRow(data2)
		arcpy.SetProgressorPosition()

	del cursor2,point_data
  
    except Exception,e:
        arcpy.AddError('%s'%(e))
        
    finally:
        
        for fname in del_files:
            try:
                arcpy.DeleteFeatures_management(fname)
            except Exception,e:
                continue

if __name__ == "__main__":        
    ###Inputs###
        
    infc = arcpy.GetParameterAsText(0)
    mask = arcpy.GetParameterAsText(1)
    mask_outline = arcpy.GetParameterAsText(2)
    outfc = arcpy.GetParameterAsText(3)
    outfc2 = arcpy.GetParameterAsText(4)
    attributes = arcpy.GetParameterAsText(5)

    main(infc,outfc,outfc2,mask,mask_outline,attributes)
