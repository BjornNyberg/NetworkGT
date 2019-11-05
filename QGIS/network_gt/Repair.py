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
    
import os, sys,math
import processing as st
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField,QgsVectorFileWriter,QgsProcessingParameterBoolean, QgsFeature, QgsPointXY,QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry,QgsSpatialIndex, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty)
from qgis.PyQt.QtGui import QIcon

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
            10.0))
        self.addParameter(QgsProcessingParameterBoolean(self.Trim,
                    self.tr("Trim"),False))
        self.addParameter(QgsProcessingParameterBoolean(self.Extend,
                    self.tr("Extend"),True))
    
    def processAlgorithm(self, parameters, context, feedback):
        
        layer = self.parameterAsSource(parameters, self.Network, context)
        T = parameters[self.Trim]
        E = parameters[self.Extend]
        fields = QgsFields()
        fields.append(QgsField("ID", QVariant.Int))
        
        (writer, dest_id) = self.parameterAsSink(parameters, self.Repaired, context,
                                               fields, QgsWkbTypes.LineString, layer.sourceCrs())
        
        infc = parameters[self.Network]
        distance = parameters[self.Distance]

        if T == True and E == True:
            feedback.pushInfo(QCoreApplication.translate('Repair Error','***NOTE*** - Algorithm will not trim extended lines'))
            feedback.pushInfo(QCoreApplication.translate('Repair Error','Rerun the repair tool on the extended fracture lines with the Trim option selected'))

        diss = st.run("native:dissolve", {'INPUT':infc,'FIELD':[],'OUTPUT':'memory:'})
        
        params = {'INPUT':diss['OUTPUT'],'LINES':diss['OUTPUT'],'OUTPUT':'memory:'}  
        templines = st.run('native:splitwithlines',params,context=context,feedback=feedback)             
        
        Graph = {} #Store all node connections
        
        feedback.pushInfo(QCoreApplication.translate('Nodes','Reading Node Information'))
        features = templines['OUTPUT'].getFeatures(QgsFeatureRequest())
        
        index = QgsSpatialIndex(templines['OUTPUT'].getFeatures())
        data = {feature.id():feature.geometry() for feature in templines['OUTPUT'].getFeatures()}
        total = 0
        for feature in features:
            try:      
                total += 1
                geom = feature.geometry().asPolyline()
                start,end = geom[0],geom[-1]
                startx,starty=start
                endx,endy=end
                branch = [(startx,starty),(endx,endy)]        
                for b in branch:
                    if b in Graph: #node count
                        Graph[b] += 1
                    else:
                        Graph[b] = 1       

            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Node Error','%s'%(e)))
                
        total = 100.0/total

        features = templines['OUTPUT'].getFeatures(QgsFeatureRequest())
        
        fet = QgsFeature() 
        feedback.pushInfo(QCoreApplication.translate('Create Lines','Extending Lines'))
        for enum,feature in enumerate(features):
            try:    
                feedback.setProgress(int(enum*total))
                geom = feature.geometry().asPolyline()
                start,end = geom[0],geom[-1]
                startx,starty=start
                endx,endy=end
                branch = [(startx,starty),(endx,endy)]
                rows = [feature.id()]
                if branch[0] == branch[1]: #delete loops
                    continue
                in_geom = feature.geometry()

                pnts = []
                ds,de = 0,0
                vertices = [Graph[branch[0]],Graph[branch[1]]]
                if T:
                    if in_geom.length() < distance and 1 in vertices: #trim short isolated lines
                        continue
                if E:
                    if vertices[0] == 1: #extend startpoint
                        near = index.nearestNeighbor(QgsPointXY(startx,starty), 3) #look for 3 closest lines
                        d = 1e10
                        for id in near:
                            if id != feature.id():
                                id_geom = data[id]
                                testGeom = QgsGeometry.fromPointXY(QgsPointXY(startx,starty))
                                dist = QgsGeometry.distance(testGeom, id_geom)
                                if dist < d and dist > 0:
                                    d = dist
                        if d < distance:
                            ds = distance

                    if vertices[1] == 1:#extend endpoint
                        near = index.nearestNeighbor(QgsPointXY(endx,endy), 3) #look for 3 closest lines
                        d = 1e10
                        for id in near:
                            if id != feature.id():
                                id_geom = data[id]
                                testGeom = QgsGeometry.fromPointXY(QgsPointXY(endx,endy))
                                dist = QgsGeometry.distance(testGeom, id_geom)
                                if dist < d and dist > 0:
                                    d = dist
                        if d < distance :
                            de = distance
                        
                    in_geom = in_geom.extendLine(ds,de)
    

                fet.setGeometry(in_geom)
                fet.setAttributes(rows)
                writer.addFeature(fet,QgsFeatureSink.FastInsert) 
 
            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Repaired Line','%s'%(e)))
        
                
        return {self.Repaired:dest_id}
