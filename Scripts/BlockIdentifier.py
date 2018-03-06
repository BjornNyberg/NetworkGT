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

import  os,arcpy

def main (network,blocks,mask,units):

    try:
        del_files = []
        arcpy.FeatureToPolygon_management([network], blocks, "","NO_ATTRIBUTES", "")
        
        arcpy.AddField_management(blocks, 'Area', 'DOUBLE')
        arcpy.AddField_management(blocks, 'Perimeter', 'DOUBLE')

        with arcpy.da.UpdateCursor(blocks,['Area','Perimeter','Shape@']) as cursor:
            for row in cursor:
                area = row[-1].getArea('PLANAR',units)
                peri = row[-1].getLength('PLANAR',units)
                row[0] = area
                row[1] = peri
                cursor.updateRow(row)    

        cursorm = [m_data for m_data in arcpy.da.SearchCursor(blocks,['SHAPE@'])]

        curfields = curfields = [f.name for f in arcpy.ListFields(mask)]

        names = [('Min_Block','Min Block Size'),('Mean_Block','Mean Block Size'),('Max_Block','Max Block Size'),('Sum_Block','Sum Block Size'),('C_Blocks','No. Blocks'),('I_Blocks','No. Intersected Blocks')]
        
	for fname in names:
            if fname[0] not in curfields:
                arcpy.AddField_management(mask, fname[0], 'DOUBLE',"","","",fname[1])

        if 'S_Radius' in curfields:
            del_files.extend(["in_memory\\fishnet_points","in_memory\\mask"])
            arcpy.FeatureToPoint_management(mask, "in_memory\\fishnet_points")
            arcpy.Buffer_analysis("in_memory\\fishnet_points","in_memory\\mask","S_Radius", "FULL", "ROUND", "NONE")
            orig = mask
            mask = "in_memory\\mask"
            update_table = {}

	names = [fname[0] for fname in names]
        names.extend(['Shape@','Sample_No_'])
            
        count = arcpy.GetCount_management(mask).getOutput(0)
        arcpy.SetProgressor("step", "Calculating Block Sizes",0,eval(count),1)    
        with arcpy.da.UpdateCursor(mask,names) as cursor:
            for row in cursor:
                try:      
                    data = []
                    Count = 0.0
                    
                    geom = row[-2]

                    for m in cursorm:
                        if geom.contains(m[0]):
                            data.append(m[0].getArea('PLANAR',units))        
                        else:
                            inter = m[0].intersect(geom,4)
                            if inter.area != 0.0:
                                Count += 1
                                data.append(inter.getArea('PLANAR',units))
                                            
                    if data:
                        if 'S_Radius' in curfields:
                            update_table[row[-1]] = (data,Count)
                        else:
                            row[0] = min(data)
                            row[1] = float(sum(data))/len(data)
                            row[2] = max(data)
                            row[3] = sum(data)
                            row[4] = len(data)
                            row[5] = Count
                            cursor.updateRow(row)    
                            
                    else:
                        if not 'S_Radius' in curfields:
                            row[0] = 0
                            row[1] = 0
                            row[2] = 0
                            row[3] = 0
                            row[4] = 0
                            row[5] = 0
                            cursor.updateRow(row)              
                    
                    
                except Exception,e:
                    arcpy.AddError('%s'%(e))
                    continue
                                            
                arcpy.SetProgressorPosition()
                                            
        del cursorm

        if 'S_Radius' in curfields:	

            with arcpy.da.UpdateCursor(orig,names) as cursor:
                for row in cursor:
                    try:
                        if row[-1] in update_table:
                            values = update_table[row[-1]]
                            data = values[0]
                            Count = values[1]
                                                                    
                            row[0] = min(data)
                            row[1] = float(sum(data))/len(data)
                            row[2] = max(data)
                            row[3] = sum(data)
                            row[4] = len(data)
                            row[5] = Count
                        else:
                            row[0] = 0
                            row[1] = 0
                            row[2] = 0
                            row[3] = 0
                            row[4] = 0
                            row[5] = 0

                        cursor.updateRow(row)              
                                     
                    except Exception,e:
                        arcpy.AddError('%s'%(e))
                        continue
                                                
                    arcpy.SetProgressorPosition()


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
        
    network = arcpy.GetParameterAsText(0) 
    mask = arcpy.GetParameterAsText(1)
    units = arcpy.GetParameterAsText(2)
    blocks = arcpy.GetParameterAsText(3)

    main(network,blocks,mask,units)
