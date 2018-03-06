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


import  arcpy,math,os
import numpy as np

def main (infc,dist,outfc,angle):

    try:

	if 'shp' in outfc:
	    arcpy.AddError('Output parameter must be saved in a geodatabase')
	    sys.exit()


        dist = eval(dist.replace(',','.'))
        
        arcpy.CreateFeatureclass_management("in_memory","gridlines","POLYLINE",'','ENABLED','',infc)
        arcpy.AddField_management("in_memory\\gridlines", 'Sample_No_',"LONG")

        extent = arcpy.Describe(infc).extent
        xmin,ymin = extent.XMin,extent.YMin
        angle = angle.replace(',','.')
        angle = eval(angle)        

        array = arcpy.Array([arcpy.Point(extent.XMin, extent.YMin),arcpy.Point(extent.XMin, extent.YMax),
                         arcpy.Point(extent.XMax, extent.YMax),arcpy.Point(extent.XMax, extent.YMin)])

        box_polyline = arcpy.Polygon(array)
            
        data = {}
        if angle == 0 or angle == 90 or angle == 180:

            if angle == 0 or angle == 180:

                x_values = np.arange(extent.XMin,extent.XMax+dist,dist)

                for enum,x in enumerate(x_values):

                    array = arcpy.Array([arcpy.Point(x,extent.YMin),arcpy.Point(x,extent.YMax)])
                    polyline = arcpy.Polyline(array)
                    geom = polyline.intersect(box_polyline,2)
                  
                    data[x] = geom
            else:

                y_values = np.arange(extent.YMin,extent.YMax+dist,dist)

                for enum,y in enumerate(y_values):

                    array = arcpy.Array([arcpy.Point(extent.XMin,y),arcpy.Point(extent.XMax,y)])
                    polyline = arcpy.Polyline(array)
                    geom = polyline.intersect(box_polyline,2)
                  
                    data[y] = geom
                
        else:            
            
            dx =(extent.XMin-extent.XMax)
            dy =(extent.YMin-extent.YMax)
            distance = math.sqrt(dx*dx + dy*dy)

            x,y = extent.XMin, extent.YMin

            angle = 90 - angle
            
            x2 = x + (distance * math.cos(math.radians(angle)))
            y2 = y + (distance * math.sin(math.radians(angle)))
            
            array = arcpy.Array([arcpy.Point(x,y),arcpy.Point(x2,y2)])
    
            polyline = arcpy.Polyline(array)
            geom = polyline.intersect(box_polyline,2)
            data[y] = geom       
    

            length = 1
            while length != 0:
                dx = x - x2
                dy = y - y2

                L = math.sqrt(dx*dx + dy*dy)
                dx /= L
                dy /= L
                x -= dist*dy
                y += dist*dx
            
                
                x2 = x + (L * math.cos(math.radians(angle)))
                y2 = y + (L * math.sin(math.radians(angle)))

                dx = x - x2
                dy = y - y2
                m = dy/dx
                b = y - m*x
                x = extent.XMin
                y = m*x+b

                dx = x - extent.XMax
                dy = y - extent.YMax
                
                L = math.sqrt(dx*dx + dy*dy) + distance
                
                x2 = x + (L * math.cos(math.radians(angle)))
                y2 = y + (L * math.sin(math.radians(angle)))

                array = arcpy.Array([arcpy.Point(x,y),arcpy.Point(x2,y2)])
                polyline = arcpy.Polyline(array)
                geom = polyline.intersect(box_polyline,2)
                
                data[y2] = geom
                length = geom.length
                
            length = 1

            dx =(extent.XMin-extent.XMax)
            dy =(extent.YMin-extent.YMax)
            L = math.sqrt(dx*dx + dy*dy)

            x,y = extent.XMin, extent.YMin
            
            x2 = x + (L * math.cos(math.radians(angle)))
            y2 = y + (L * math.sin(math.radians(angle)))
            
            while length != 0:
                dx = x - x2
                dy = y - y2

                L = math.sqrt(dx*dx + dy*dy)
                dx /= L
                dy /= L
                x += dist*dy
                y -= dist*dx
            
                
                x2 = x + (L * math.cos(math.radians(angle)))
                y2 = y + (L * math.sin(math.radians(angle)))

                dx = x - x2
                dy = y - y2
                m = dy/dx
                b = y - m*x
                x = extent.XMin
                y = m*x+b

                dx = x - extent.XMax
                dy = y - extent.YMax
                
                L = math.sqrt(dx*dx + dy*dy) + distance
                
                x2 = x + (L * math.cos(math.radians(angle)))
                y2 = y + (L * math.sin(math.radians(angle)))

                array = arcpy.Array([arcpy.Point(x,y),arcpy.Point(x2,y2)])
                polyline = arcpy.Polyline(array)
                geom = polyline.intersect(box_polyline,2)
                
                data[y2] = geom
                length = geom.length


        with arcpy.da.InsertCursor("in_memory\\gridlines",['SHAPE@']) as cursor: #Create and order lines
            for d in sorted(data):
                v = [data[d]]
                
                cursor.insertRow(v)

	del cursor,data

        arcpy.MakeFeatureLayer_management("in_memory\\gridlines", "in_memory\\layer")
        arcpy.SelectLayerByLocation_management("in_memory\\layer", "INTERSECT", infc)
        arcpy.CopyFeatures_management("in_memory\\layer", outfc)
        
        with arcpy.da.UpdateCursor(outfc,['Sample_No_']) as cursor:
 
            for enum,row in enumerate(cursor):
                try:
                    row[0] = enum

                    cursor.updateRow(row)
                            
                except Exception,e:
                    arcpy.AddError('%s'%(e))
                    continue

    except Exception,e:
        arcpy.AddError('%s'%(e))
        
    finally:
        del_files = ["in_memory\\gridlines"]
        for fname in del_files:
            try:
                arcpy.DeleteFeatures_management(fname)
            except Exception,e:
                continue
	        
if __name__ == "__main__":        
    ###Inputs###
        
    infc = arcpy.GetParameterAsText(0)
    rows = arcpy.GetParameterAsText(1)
    angle = arcpy.GetParameterAsText(2)
    outfc = arcpy.GetParameterAsText(3)

    main(infc,rows,outfc,angle)

