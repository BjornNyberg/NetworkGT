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

import arcpy,sys
                     
def main (infc,infc2,infc3):
    try:

        clusters = {}
	isolated_clusters = {}
        branches = {}
        nodes = {}
        enodes = {}

        curfields = [f.name for f in arcpy.ListFields(infc)]
        
        new_fields = {'No_W_B':'No. Whole Blocks','No_T_B':'No. Theoretical Blocks','B_Size':'Average Theoretical Block Size'}
        
        if 'Sample_No_' not in curfields:
            arcpy.AddError("Topology Dataset input is invalid - Run Topology Parameters tool prior to Block Analysis tool")
            sys.exit()
        curfields2 = [f.name for f in arcpy.ListFields(infc2)]
        if 'Cluster' not in curfields2 or 'B_Weight' not in curfields2:
            arcpy.AddError("Cluster input is invalid - Run Clustering tool (Dissolved Branches -unchecked and Split Clusters - checked) prior to Block Analysis tool")
            sys.exit()
            
        curfields2 = [f.name for f in arcpy.ListFields(infc3)]
        if 'Sample_No_' not in curfields2:
            arcpy.AddError("Nodes input is invalid - Run Branches and Nodes tool prior to Block Analysis tool")
            sys.exit()
                
        for k,v in new_fields.iteritems():
            if k not in curfields:
                arcpy.AddField_management(infc, k, "DOUBLE","","","",v)

	arcpy.MakeFeatureLayer_management(infc2, "in_memory\\layer")
	arcpy.SelectLayerByAttribute_management("in_memory\\layer", "NEW_SELECTION", "Connection = 'C - C' OR Connection = 'C - I' OR Connection = 'C - U'")
		
        arcpy.Dissolve_management("in_memory\\layer", "in_memory\\clusters", dissolve_field="Sample_No_;Cluster", statistics_fields="B_Weight SUM;B_Weight COUNT", multi_part="MULTI_PART", unsplit_lines="DISSOLVE_LINES")
	
	if infc.endswith('.shp'):
	    curfields = ['Sample_No_','COUNT_B_We','SUM_B_Weig']
	else:
	    curfields = ['Sample_No_','COUNT_B_Weight','SUM_B_Weight']

	with arcpy.da.SearchCursor("in_memory\\clusters",curfields) as cursor:
            for row in cursor:
                if row[2] != 1:
                    if row[0] not in clusters:
                        clusters[row[0]] = 1
                        isolated_clusters[row[0]] = 0
                        branches[row[0]] = row[1]
                    else:
                        cluster = clusters[row[0]]
                        cluster += 1
                        clusters[row[0]] = cluster
                        b = branches[row[0]]
                        b += row[1]
                        branches[row[0]] = b

                    if row[1] - row[2] != 0:

                        icluster = isolated_clusters[row[0]]
                        icluster += 1
                        isolated_clusters[row[0]] = icluster		 
        
        arcpy.MakeFeatureLayer_management(infc3, "in_memory\\nodes")
        arcpy.SelectLayerByLocation_management("in_memory\\nodes", 'intersect', "in_memory\\clusters","0.01 Meters",)

        with arcpy.da.SearchCursor("in_memory\\nodes",['Sample_No_','Class']) as cursor:
            for row in cursor:
                if row[0] not in nodes:
                    nodes[row[0]] = 1
                    enodes[row[0]] = 0
                    
                else:
                    curValue = nodes[row[0]]
                    curValue += 1
                    nodes[row[0]] = curValue
                if row[1] == 'E':
                    en = enodes[row[0]]
                    en += 1
                    enodes[row[0]] = en
   
        with arcpy.da.UpdateCursor(infc,['Sample_No_','Area','No_W_B','No_T_B','B_Size']) as cursor:
            for row in cursor:
                if row[0] in clusters:
		    try:
			num_n = nodes[row[0]]
			num_en = enodes[row[0]]
		        num_b = branches[row[0]]
			num_c = clusters[row[0]]
			num_ic = isolated_clusters[row[0]]			
		        blocks = num_b - num_n + num_c

			if num_ic > 0:
			    tb = ((num_en - num_ic + 1) / 2.0) + blocks
			else:
			    tb = blocks

                        row[-3] = blocks
                        row[-2] = tb
			if tb > 0:
                            row[-1] = row[1]/tb
			else:
			    row[-1] = 0
	
		    except Exception,e:
			arcpy.AddMessage('%s'%(e))
			continue
                else:
                    row[-3] = 0
                    row[-2] = 0
                    row[-1] = 0
                cursor.updateRow(row)

    except Exception,e:
        arcpy.AddError('%s'%(e))

    finally:
        del_files = ["in_memory\\clusters"]
        for fname in del_files:
            try:
                arcpy.DeleteFeatures_management(fname)
            except Exception:
                continue
        

if __name__ == "__main__":        
    ###Inputs###
        
    infc = arcpy.GetParameterAsText(0)
    infc2 = arcpy.GetParameterAsText(1)
    infc3 = arcpy.GetParameterAsText(2)

    main(infc,infc2,infc3)
