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

import arcpy,os,numpy,sys
                     
def main (infc,outfc,units,dissolve,connected,split):
    try:
        del_files = ["in_memory\\cluster","in_memory\\cluster_diss"]
        
        #Parameter check
        if dissolve == 'true' or connected == 'true' or split == 'true':
            curfields = [f.name for f in arcpy.ListFields(infc)]
            if 'Connection' not in curfields:
                arcpy.AddError("Run Branches and Nodes tool prior to clustering or uncheck all options")
                sys.exit()
	if connected == 'true':
            arcpy.MakeFeatureLayer_management(infc, "in_memory\\layer")
            arcpy.SelectLayerByAttribute_management("in_memory\\layer", "NEW_SELECTION", "Connection = 'C - C' OR Connection = 'C - I' OR Connection = 'C - U'")
            infc = "in_memory\\layer"

        arcpy.env.overwriteOutput = True  
        arcpy.AddMessage('Clustering Network')
        arcpy.Buffer_analysis(infc,"in_memory\\cluster","0.01 Meters", "FULL", "ROUND", "NONE")
        curfields = [f.name for f in arcpy.ListFields(infc)]

        if split == 'true':
            arcpy.Dissolve_management("in_memory\\cluster", "in_memory\\cluster_diss" , "Sample_No_", "", "SINGLE_PART")
            fields = ["Length","Shape@",'Sample_No_','Sample_No1']
        else:
            arcpy.Dissolve_management("in_memory\\cluster", "in_memory\\cluster_diss" , "", "", "SINGLE_PART")
            fields = ["Length","Shape@"]

        curfields2 = [f.name for f in arcpy.ListFields("in_memory\\cluster_diss")]

        if 'Cluster' not in curfields2:
            arcpy.AddField_management("in_memory\\cluster_diss", "Cluster", "LONG")

        if 'Length' not in curfields2:
            arcpy.AddField_management("in_memory\\cluster_diss", "Length", "DOUBLE")

             
        with arcpy.da.UpdateCursor("in_memory\\cluster_diss",["Cluster"]) as cursor:
            for enum,row in enumerate(cursor):
                row[0] = enum
                cursor.updateRow(row)

        if dissolve == 'true':
	    del_files.append("in_memory\\cluster_sj")
            sj = "in_memory\\cluster_sj"
        else:
            sj = outfc

        arcpy.SpatialJoin_analysis(infc, "in_memory\\cluster_diss",sj, "JOIN_ONE_TO_MANY")
        with arcpy.da.UpdateCursor(sj,fields) as cursor:
            for row in cursor:
                if split == 'true':
                    if row[2] != row[3]:
                        cursor.deleteRow()
                        continue
                row[0] = row[1].getLength('PLANAR',units)
                cursor.updateRow(row)

        if dissolve == 'true':
            arcpy.Dissolve_management(sj, outfc,['Cluster','Sample_No_'],[['Length','Min'],['Length','Mean'],['Length','Max'],['Length','Count']],"MULTI_PART")

            pvt_table = os.path.join('in_memory','pvt_'+os.path.basename(outfc))
	
	    del_files.append(pvt_table)

            arcpy.PivotTable_management(sj,['Cluster','Sample_No_'], 'Connection', 'Length', pvt_table)
            fields = [f.name for f in arcpy.ListFields(pvt_table)[3:]]
            curfields = [f.name for f in arcpy.ListFields(outfc)]

            data = {}
            
            arcpy.AddMessage('Creating Fields')
            update_fields = []
            data_names = ['MIN','MEAN','MAX','SUM','COUNT']
            for enum,fname in enumerate(fields):            
                for s in data_names:
                    alias = fname.replace('___',' - ')
                    name_a = '%s '%(alias) + s
                    name = '%s_'%(fname) + s[:4]
                    if name not in curfields:
                        arcpy.AddField_management(outfc,name,'DOUBLE',"","","",name_a)
                    update_fields.append(name)

            data = {}
	    fields.extend(['Cluster','Sample_No_'])
	    update_fields.extend(['Cluster','Sample_No_'])
            arcpy.AddMessage('Reading Data')
            with arcpy.da.SearchCursor(pvt_table,fields) as cursor:
                for row in cursor:
                    ID = (row[-1],row[-2])
                    if ID not in data:
                        values = {}
                        for enum,field in enumerate(fields[:-2]):
                            values[field] = []
                            if row[enum] > 0 :
                                values[field] += [row[enum]]                  
                        data[ID] = values
                    else:
                        values = data[ID]
                        for enum,field in enumerate(fields[:-2]):
                            if row[enum] > 0:            
                                values[field] += [row[enum]]
                                
                        data[ID] = values

            
            arcpy.AddMessage('Updating Feature Class')
            with arcpy.da.UpdateCursor(outfc,update_fields) as cursor:
                for row in cursor:
                    try:
                        C = 0
                        
                        ID = (row[-2],row[-1])
                        values = data[ID]

                        for field in fields[:-2]:
                            v = values[field]
                            if v:
                                row[C] = min(v)
                                C += 1
                                row[C] = numpy.mean(v)
                                C += 1
                                row[C] = max(v)
                                C += 1
                                row[C] = sum(v)
                                C += 1
                                row[C] = len(v)
                                C += 1
				
                            else:                
                                for n in range(5):
                                    row[C] = 0
                                    C+= 1
         
                        cursor.updateRow(row)
                    except Exception,e:
                        arcpy.AddMessage('%s'%(e))
                        continue

        else:
            delfields = []

            for field in arcpy.ListFields(outfc):
                fname = field.name
                if not field.required:
                    if fname not in curfields:
                        delfields.append(fname)
                        
            delfields.remove('Cluster')
            arcpy.DeleteField_management(sj,delfields)

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
    units = arcpy.GetParameterAsText(1)
    outfc = arcpy.GetParameterAsText(2)
    dissolve = arcpy.GetParameterAsText(3)
    connected = arcpy.GetParameterAsText(4)
    split = arcpy.GetParameterAsText(5)

    main(infc,outfc,units,dissolve,connected,split)
