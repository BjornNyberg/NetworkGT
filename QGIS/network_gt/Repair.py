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
    
import os, sys
import processing as st
import networkx as nx
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField,QgsVectorFileWriter,QgsVectorLayer,QgsMultiLineString,QgsProcessingParameterField,QgsProcessingParameterBoolean, QgsFeature, QgsPointXY,QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry,QgsSpatialIndex, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty)
from qgis.PyQt.QtGui import QIcon
from math import ceil

class RepairTool(QgsProcessingAlgorithm):

    Network='Network'
    Repaired='Output'
    Distance = 'Distance'
    Trim = 'Trim'
    Extend = 'Extend'
    
    def __init__(self):
        super().__init__()
        
    def name(self):
        return "Repair Topology"

    def tr(self, text):
        return QCoreApplication.translate("Repair Topology", text)

    def displayName(self):
        return self.tr("Repair Topology")
 
    def group(self):
        return self.tr("Topology")
    
    def shortHelpString(self):
        return self.tr("Repairs common topological erros in the digitisation of a fracture network")

    def groupId(self):
        return "Topology"
    
    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT"
    
    def createInstance(self):
        return type(self)()

    def icon(self):
        pluginPath = os.path.join(os.path.dirname(__file__),'icons')
        return QIcon( os.path.join( pluginPath, 'RT.jpg') )
    
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Network"),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.Repaired,
            self.tr("Repaired"),
            QgsProcessing.TypeVectorLine))
        self.addParameter(QgsProcessingParameterNumber(
            self.Distance,
            self.tr("Distance to Extend/Trim"),
            QgsProcessingParameterNumber.Double,
            0.5))
        self.addParameter(QgsProcessingParameterBoolean(self.Trim,
                    self.tr("Trim"),True))
        self.addParameter(QgsProcessingParameterBoolean(self.Extend,
                    self.tr("Extend"),True))
    
    def processAlgorithm(self, parameters, context, feedback):
        
        layer = self.parameterAsLayer(parameters, self.Network, context)
        T = parameters[self.Trim]
        E = parameters[self.Extend]

        P = 100000 #Precision
        pr = layer.dataProvider()
        
        if layer.fields().indexFromName('Fault No') == -1:
            pr.addAttributes([QgsField('Fault No', QVariant.Double)])
            layer.updateFields()

        f_len = layer.fields().indexFromName('Fault No')
        layer.startEditing()                             
        for feature in layer.getFeatures():
            pr.changeAttributeValues({feature.id():{f_len:feature.id()}})
        layer.commitChanges() 
        
        infc = parameters[self.Network]
        distance = parameters[self.Distance]
        params = {'INPUT':infc,'OUTPUT':'memory:'}  
        mpsp = st.run("native:multiparttosingleparts",params,context=context,feedback=feedback) 
        params = {'INPUT':mpsp['OUTPUT'],'LINES':mpsp['OUTPUT'],'OUTPUT':'memory:'}
        params = {'INPUT':mpsp['OUTPUT'],'LINES':infc,'OUTPUT':'memory:'}  
        templines = st.run('native:splitwithlines',params,context=context,feedback=feedback)             
        
        Graph = {} #Store all node connections
        
        feedback.pushInfo(QCoreApplication.translate('Nodes','Reading Node Information'))
        features = templines['OUTPUT'].getFeatures(QgsFeatureRequest())
        
        index = QgsSpatialIndex(templines['OUTPUT'].getFeatures())
        data = {feature.id():feature for feature in templines['OUTPUT'].getFeatures()}
        total = 0
        
        fields = QgsFields()
        for field in layer.fields():
            fields.append(QgsField(field.name(),field.type()))

        (writer, dest_id) = self.parameterAsSink(parameters, self.Repaired, context,
                                               fields, QgsWkbTypes.MultiLineString, layer.sourceCrs())
        
        for feature in features:
            try:      
                geom = feature.geometry().asPolyline()
                start,end = geom[0],geom[-1]
                startx,starty=start
                endx,endy=end
                branch = [(ceil(startx*P)/P,ceil(starty*P)/P),(ceil(endx*P)/P,ceil(endy*P)/P)]        
                for b in branch:
                    if b in Graph: #node count
                        Graph[b] += 1
                    else:
                        Graph[b] = 1       

            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Node Error','%s'%(e)))
                
        features = templines['OUTPUT'].getFeatures(QgsFeatureRequest())

        edges = {}
        attrs = {}
        extended = set([])
        if E:
            feedback.pushInfo(QCoreApplication.translate('Create Lines','Extending Line Geometries'))
        else:
            fet = QgsFeature()
            feedback.pushInfo(QCoreApplication.translate('Create Lines','Creating Line Geometries'))
        for feature in features:
            try:    
                geomFeat = feature.geometry()
                geom = geomFeat.asPolyline()
                start,end = geom[0],geom[-1]
                startx,starty=start
                endx,endy=end
                branch = [(ceil(startx*P)/P,ceil(starty*P)/P),(ceil(endx*P)/P,ceil(endy*P)/P)]  
            
                fID = feature['Fault No'] 
 
                if branch[0] == branch[1]: #delete loops
                    continue

                ds,de = 0,0
                vertices = [Graph[branch[0]],Graph[branch[1]]]
                
                if T:
                    if geomFeat.length() < distance and 1 in vertices: #trim short isolated lines
                        continue
                    if E == False:
                        rows = []
                        for field in layer.fields():
                            rows.append(feature[field.name()])
                            
                        fet.setGeometry(geomFeat)
                        fet.setAttributes(rows)
                        writer.addFeature(fet,QgsFeatureSink.FastInsert) 
                        continue
                    
                if E:
                    if vertices[0] == 1:
                        testGeom = geomFeat.extendLine(distance,0)
                        near = index.nearestNeighbor(QgsPointXY(startx,starty), 2) #look for x closest lines
                        ds = 0
                        for nid in near:
                            value = data[nid]
                            inFID = value['Fault No']
                            if inFID != fID:
                                id_geom = value.geometry()
                                if testGeom.intersects(id_geom):
                                    ds = distance
                                    break
            
                    if vertices[1] == 1:
                        testGeom2 = geomFeat.extendLine(0,distance)
                        near = index.nearestNeighbor(QgsPointXY(endx,endy), 2) #look for x closest lines
                        de = 0

                        for nid in near:
                            value = data[nid]
                            inFID = value['Fault No']
  
                            if inFID != fID:
                                id_geom = value.geometry()
                                if testGeom2.intersects(id_geom):
                                    de = distance
                                    break
                                    
                    if ds > 0 or de > 0:
                        geomFeat = geomFeat.extendLine(ds,de)
                        extended.update([fID])
                    
                    if fID not in attrs:
                        rows = []
                        for field in layer.fields():
                            rows.append(feature[field.name()])
                        attrs[fID] = rows
                        
                    part = geomFeat.asPolyline()
                    startx2 = None
                    
                    for point in part:
                        if startx2 == None:	
                            startx2,starty2 = (ceil(point.x()*P)/P,ceil(point.y()*P)/P)
                            continue
                        endx2,endy2 = (ceil(point.x()*P)/P,ceil(point.y()*P)/P)

                        if fID not in edges:
                            nGraph = nx.Graph()
                            edges[fID] = nGraph  
                            
                        edges[fID].add_edge((startx2,starty2),(endx2,endy2),weight=1)
                        startx2,starty2 = endx2,endy2
  
            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Repaired Line','%s'%(e)))
        if E:
            vl = QgsVectorLayer("LineString?crs=%s"%(layer.sourceCrs().authid() ), "tempLines", "memory")        
            fet = QgsFeature()
            pr = vl.dataProvider()
            pr.addAttributes([QgsField("FID", QVariant.Int)])
            vl.startEditing()
            for FID,Graph in edges.items(): #Define order of line segments
                
                for c in nx.connected_components(Graph):
                    G = Graph.subgraph(c)
                    source = list(G.nodes())[0]
                    for n in range(2):
                        length,path = nx.single_source_dijkstra(G,source,weight='weight')
                        Index = max(length,key=length.get)
                        source = path[Index][-1]
                        
                    points = []    
                    for p in path[Index]:
                        points.append(QgsPointXY(p[0],p[1]))
        
                    rows = [FID] 
                    fet.setGeometry(QgsGeometry.fromPolylineXY(points))
                    fet.setAttributes(rows)
                    pr.addFeatures([fet])

            vl.commitChanges()
            
            params = {'INPUT':vl,'LINES':vl,'OUTPUT':'memory:'}  
            templines = st.run('native:splitwithlines',params,context=context,feedback=feedback)      
            del vl
            edges,Graph = {},{}
            total = 0

            for feature in templines['OUTPUT'].getFeatures(QgsFeatureRequest()):
                try:      
                    total += 1
                    geom = feature.geometry().asPolyline()
                    start,end = geom[0],geom[-1]
                    startx,starty=start
                    endx,endy=end
                    branch = [(ceil(startx*P)/P,ceil(starty*P)/P),(ceil(endx*P)/P,ceil(endy*P)/P)]        
                    for b in branch:
                        if b in Graph: #node count
                            Graph[b] += 1
                        else:
                            Graph[b] = 1       

                except Exception as e:
                    feedback.reportError(QCoreApplication.translate('Node Error','%s'%(e)))
            
            if total > 0:
                total = 100.0/total

            outData = {}

            feedback.pushInfo(QCoreApplication.translate('Create Lines','Creating Line Geometries'))
            for enum,feature in enumerate(templines['OUTPUT'].getFeatures(QgsFeatureRequest())):
                try:    
                    if total > 0:
                        feedback.setProgress(int(enum*total))
                    geomFeat = feature.geometry()
                    geom = geomFeat.asPolyline()
                    start,end = geom[0],geom[-1]
                    startx,starty=start
                    endx,endy=end
                    branch = [(ceil(startx*P)/P,ceil(starty*P)/P),(ceil(endx*P)/P,ceil(endy*P)/P)]  
                
                    fID = feature['FID'] 

                    vertices = [Graph[branch[0]],Graph[branch[1]]]

                    if geomFeat.length() < distance*1.5 and 1 in vertices and fID in extended: #trim short extended lines
                            continue

                    if fID not in outData:
                        outData[fID] = []

                    outData[fID].append(geomFeat)    
                    
                except Exception as e:
                    feedback.reportError(QCoreApplication.translate('Repaired Line','%s'%(e)))
            
            for k,v in outData.items():
                rows = attrs[k]   
                outGeom = []
                for geom in v:
                    lineString = geom.asPolyline()
                    outGeom.append(lineString)
                polyline = QgsGeometry.fromMultiPolylineXY(outGeom)
                fet.setGeometry(polyline)
                fet.setAttributes(rows)
                writer.addFeature(fet,QgsFeatureSink.FastInsert) 
        
        return {self.Repaired:dest_id}
