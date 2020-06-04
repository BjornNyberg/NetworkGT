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


import  arcpy,os
import networkx as nx

def main (infc,sampling,mask,outfc,trim):
	
    try:


        if 'shp' in outfc:
    	    arcpy.AddError('Output parameter must be saved in a geodatabase')
    	    sys.exit()


        dname = os.path.dirname(outfc)
        fname = os.path.basename(outfc)

        if mask:
            arcpy.Intersect_analysis([sampling,mask], "in_memory\\lines", "ONLY_FID", "", "")
            arcpy.MultipartToSinglepart_management("in_memory\\lines","in_memory\\lines_sp")
            sampling = "in_memory\\lines_sp"

        dfields = []
        for field in arcpy.ListFields(sampling):
            if not field.required:
                dfields.append(field.name)

        arcpy.DeleteField_management(sampling,dfields)

        curfields = [f.name for f in arcpy.ListFields(sampling)]
        
        if 'Sample_No_' not in curfields:
            arcpy.AddField_management(sampling,'Sample_No_','DOUBLE')

        with arcpy.da.UpdateCursor(sampling,['OID@','Sample_No_']) as cursor:
            for feature in cursor:
                try:
                    feature[1]=feature[0]
                    cursor.updateRow(feature)
                    
                except Exception,e: #No Connection?
                    arcpy.AddError('%s'%(e))
                    continue
	
	del cursor,feature

        arcpy.FeatureVerticesToPoints_management(sampling, "in_memory\\start", "START")
        sources = {}
        with arcpy.da.SearchCursor("in_memory\\start",['SHAPE@','Sample_No_']) as cursor:
            for feature in cursor:
                    start = feature[0].firstPoint
                    start = (round(start.X,4),round(start.Y,4))
                    sources[feature[1]] = start

	del cursor,feature

        infields = [(f.name,f.type) for f in arcpy.ListFields(infc)]

        arcpy.Intersect_analysis ([sampling,infc], "in_memory\\int", "","","POINT")
                                             
        arcpy.SplitLineAtPoint_management(sampling, "in_memory\\int", outfc, 1)

        curfields = [f.name for f in arcpy.ListFields(outfc)]
                                             
        if 'Distance' not in curfields:         
            arcpy.AddField_management(outfc,'Distance',"DOUBLE")

        if 'Count' not in curfields:         
            arcpy.AddField_management(outfc,'Count',"SHORT")

        
        edges = {}
        points = []
        arcpy.CreateFeatureclass_management("in_memory","point","POINT",'','ENABLED','',infc)

        
        arcpy.AddMessage('Calculating Edges')
        with arcpy.da.InsertCursor("in_memory\\point",["SHAPE@"]) as cursor2:  
            with arcpy.da.SearchCursor(outfc,['SHAPE@','Sample_No_']) as cursor:
		
                for feature in cursor:
                    start = feature[0].firstPoint
                    end = feature[0].lastPoint
                    pnts1,pnts2 = [(round(start.X,4),round(start.Y,4)),(round(end.X,4),round(end.Y,4))]
                    Length = feature[0].length
                    ID = feature[1]

                    if ID in edges:
                        edges[ID].add_edge(pnts1,pnts2,weight=Length)
                    else:
                        G = nx.Graph()
                        G.add_edge(pnts1,pnts2,weight=Length)
                        edges[ID] = G

                    if pnts1 not in points:
                        points.append(pnts1)
                        cursor2.insertRow([pnts1])

                    if pnts2 not in points:
                        points.append(pnts2)
                        cursor2.insertRow([pnts2])  

	del cursor,cursor2,feature,G
        
        arcpy.SpatialJoin_analysis ("in_memory\\point", infc, "in_memory\\sj","","KEEP_COMMON")

        data = {}

        fields = []
        for field,ftype in infields:
            if field != 'SHAPE@' and ftype != 'OID' and field not in curfields:
                arcpy.AddField_management(outfc,field,ftype)
                fields.append(field)
        
        fields.append('Shape@')
        with arcpy.da.SearchCursor("in_memory\\sj", fields) as cursor:
            for feature in cursor:
                d = {}
                start = feature[-1].firstPoint
                start = (round(start.X,4),round(start.Y,4))
                for enum,field in enumerate(fields[:-1]):
                    d[field] = feature[enum]
                data[start] = d
	del cursor,feature

        
        Lengths = {}

        fields.extend(['Distance','Sample_No_','Count'])

        arcpy.AddMessage('Updating Features')
        with arcpy.da.UpdateCursor(outfc,fields) as cursor:
            for feature in cursor:
                try:
        
                    start = feature[-4].firstPoint
                    end = feature[-4].lastPoint
                    startx,starty =(round(start.X,4),round(start.Y,4))
                    endx,endy =(round(end.X,4),round(end.Y,4))
            
                    ID = feature[-2]
                    
                    if ID not in Lengths:
                        G = edges[ID]
                        Source = sources[ID]
                        
                        Length,Path = nx.single_source_dijkstra(G,Source,weight='weight')
                        Index = max(Length,key=Length.get)
                        
                        Lengths[ID] = [Length]
                        Length,Path = nx.single_source_dijkstra(G,Source,weight='weight')
                        G.clear()
                        Lengths[ID].append(Length)
                        
                    L = [Lengths[ID][0][(endx,endy)],Lengths[ID][0][(startx,starty)]]

                    feature[-3]=max(L)
		    feature[-1]= 1

                    v = L.index(max(L))

                    if v == 1:
                        FID = (startx,starty)
                    else:
                        FID = (endx,endy)
                    
                    if FID in data:   
                        d = data[FID]
                        for enum,field in enumerate(fields[:-4]):
                            if field in d:
                                feature[enum] = d[field]

                    cursor.updateRow(feature)
                except Exception,e: #No Connection?
                    arcpy.AddError('%s'%(e))
                    break
	del cursor,feature

        if trim == 'true':
            arcpy.AddMessage('Triming Lines')
            
            trim_dist = {}
            with arcpy.da.SearchCursor(outfc, ["Sample_No_","Distance"]) as cursor:
                for feature in cursor:
                    ID = feature[0]
                    dist = feature[1]
                    if ID in trim_dist:
                        if dist < trim_dist[ID]:
                            trim_dist[ID] = dist
                    else:
                        trim_dist[ID] = dist
	    del cursor,feature

            arcpy.TrimLine_edit(outfc)

            with arcpy.da.UpdateCursor(outfc,["Sample_No_","Distance"]) as cursor:
                for feature in cursor:
                    try:
                        ID = feature[0]
                        dist = feature[1] - trim_dist[ID]

                        feature[1] = dist
            
                        cursor.updateRow(feature)
                    except Exception,e: #No Connection?
                        arcpy.AddError('%s'%(e))
                        break
	    del cursor,feature

                
    except Exception,e:
        arcpy.AddError('%s'%(e))
        
    finally:
        del_files = ["in_memory\\start","in_memory\\int","in_memory\\sj","in_memory\\point","in_memory\\lines","in_memory\\lines_sp"]
        for fname in del_files:
            try:
                arcpy.DeleteFeatures_management(fname)
            except Exception,e:
                continue

if __name__ == "__main__":        
    ###Inputs###
        
    network = arcpy.GetParameterAsText(0)
    sampling = arcpy.GetParameterAsText(1)
    mask = arcpy.GetParameterAsText(2)
    outfc = arcpy.GetParameterAsText(3)
    trim = arcpy.GetParameterAsText(4)

    main(network,sampling,mask,outfc,trim)

