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
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature, QgsPointXY, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty)
from qgis.PyQt.QtGui import QIcon

class BranchesNodes(QgsProcessingAlgorithm):

    Network='Network'
    Sample_Area='Sample Area'
    IB = 'Interpretation Boundary'
    Branches='Branches'
    Nodes='Nodes'
    
    def __init__(self):
        super().__init__()
        
    def name(self):
        return "Branches and Nodes"

    def tr(self, text):
        return QCoreApplication.translate("Branches_Nodes", text)

    def displayName(self):
        return self.tr("Branches and Nodes")
 
    def group(self):
        return self.tr("Topology")
    
    def shortHelpString(self):
        return self.tr("Create branches and nodes of a fracture network")

    def groupId(self):
        return "Topology"
    
    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/blob/master/QGIS/README.pdf"
    
    def createInstance(self):
        return type(self)()

    def icon(self):
        pluginPath = os.path.join(os.path.dirname(__file__),'icons')
        return QIcon( os.path.join( pluginPath, 'BN.jpg') )
    
    def initAlgorithm(self, config):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Network"),
            [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Sample_Area,
            self.tr("Sample Area"),
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.IB,
            self.tr("Interpretation Boundary"),
            [QgsProcessing.TypeVectorPolygon], optional=True))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.Branches,
            self.tr("Branches"),
            QgsProcessing.TypeVectorLine))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.Nodes,
            self.tr("Nodes"),
            QgsProcessing.TypeVectorPoint))
    
    def processAlgorithm(self, parameters, context, feedback):
        
        layer = self.parameterAsSource(parameters, self.Network, context)
        Sample_Area = self.parameterAsSource(parameters, self.Sample_Area, context)
        
        field_check = Sample_Area.fields().indexFromName('Sample_No_')
            
        if field_check == -1:
            editLayer = self.parameterAsLayer(parameters, self.Sample_Area, context)
            pr = editLayer.dataProvider()   
            pr.addAttributes([QgsField('Sample_No_', QVariant.Int)])
            editLayer.updateFields()
            f_len = editLayer.fields().indexFromName('Sample_No_')
            editLayer.startEditing()                             
            for feature in editLayer.getFeatures():
                pr.changeAttributeValues({feature.id():{f_len:feature.id()}})
            editLayer.commitChanges() 
        
        infc = parameters[self.Network]
        infc2 = parameters[self.IB]
        infc3 = parameters[self.Sample_Area]
        
        fields = QgsFields()
        fields.append(QgsField("Class", QVariant.String))
        fields.append(QgsField("Connection", QVariant.String))
        fields.append(QgsField("Weight", QVariant.Double))
        fields.append(QgsField("Sample_No_", QVariant.Int))
        fields.append(QgsField("Length", QVariant.Double))

        (writer, dest_id) = self.parameterAsSink(parameters, self.Branches, context,
                                               fields, QgsWkbTypes.LineString, layer.sourceCrs())
        
        fields2 = QgsFields()
        fields2.append(QgsField("Class", QVariant.String))
        fields2.append(QgsField("Sample_No_", QVariant.Int))

        (writer2, dest_id2) = self.parameterAsSink(parameters, self.Nodes, context,
                                           fields2, QgsWkbTypes.Point, layer.sourceCrs())
        
        feedback.pushInfo(QCoreApplication.translate('TempFiles','Creating Temporary Files'))
        if infc2:
            params = {'INPUT':infc2,'OUTPUT':'memory:'}  
            tempmask = st.run('qgis:polygonstolines',params,context=context,feedback=feedback)                   
            params = {'INPUT':infc,'OVERLAY':infc2,'INPUT_FIELDS':'','OVERLAY_FIELDS':'','OUTPUT':'memory:'}   
            tempint = st.run('native:intersection',params,context=context,feedback=feedback)
            cursorm = [feature.geometry() for feature in tempmask['OUTPUT'].getFeatures(QgsFeatureRequest())]
            infc = tempint['OUTPUT']
            
        params = {'INPUT':infc,'LINES':infc,'OUTPUT':'memory:'}  
        templines = st.run('native:splitwithlines',params,context=context,feedback=feedback)   
        
        field_check = Sample_Area.fields().indexFromName('Radius')
        
        if field_check != -1:
            params = {'INPUT':infc3,'ALL_PARTS':False,'OUTPUT':'memory:'} 
            centroids = st.run('native:centroids',params,context=context,feedback=feedback) 
            
            params = {'INPUT':centroids['OUTPUT'],'DISTANCE':QgsProperty.fromField('Radius'), 'SEGMENTS': 100, 'END_CAP_STYLE':0,'JOIN_STYLE':0,'MITER_LIMIT':2,'DISSOLVE':False,'OUTPUT':'memory:'}
            buff = st.run('native:buffer',params,context=context,feedback=feedback)

            if infc2:
                params = {'INPUT':buff['OUTPUT'],'OVERLAY':infc2,'INPUT_FIELDS':'','OVERLAY_FIELDS':'','OUTPUT':'memory:'}   
                samplemask = st.run('native:intersection',params,context=context,feedback=feedback)   
                Sample_Area = samplemask['OUTPUT']
            else:
                Sample_Area = buff['OUTPUT']
            
            
        unknown_nodes,point_data = [],[]
        c_points = {}   
        Graph = {} #Store all node connections
        P = 6
        feedback.pushInfo(QCoreApplication.translate('Nodes','Reading Node Information'))

        features = templines['OUTPUT'].getFeatures(QgsFeatureRequest())
        total = 0
        for feature in features:
            try:      
                total += 1
                geom = feature.geometry().asPolyline()
                start,end = geom[0],geom[-1]
                startx,starty=start
                endx,endy=end
                branch = [(round(startx,P),round(starty,P)),(round(endx,P),round(endy,P))]          
                for b in branch:
                    if b in Graph: #node count
                        Graph[b] += 1
                    else:
                        Graph[b] = 1
            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Interpretation Boundary','%s'%(e)))

        if infc2:
            feedback.pushInfo(QCoreApplication.translate('Nodes','Reading Unknown Nodes'))
            features = layer.getFeatures(QgsFeatureRequest())
            for feature in features:
                try:
                    for m in cursorm:
                        if feature.geometry().intersects(m):
                            geom = feature.geometry().intersection(m)
                            if QgsWkbTypes.isSingleType(geom.wkbType()):
                                x,y = geom.asPoint()
                                unknown_nodes.append((round(x,P),round(y,P)))   
                            else:
                                for x,y in geom.asMultiPoint(): #Check for multipart polyline
                                    unknown_nodes.append((round(x,P),round(y,P)))       
                except Exception as e:
                    feedback.reportError(QCoreApplication.translate('Interpretation Boundary','%s'%(geom.wkbType())))
                    
        total = 100.0/total
        cursorm = [(feature.geometry(),feature['Sample_No_']) for feature in Sample_Area.getFeatures(QgsFeatureRequest())]
        fet = QgsFeature(fields) 
        fet2 = QgsFeature(fields)
        
        features = templines['OUTPUT'].getFeatures(QgsFeatureRequest())
        feedback.pushInfo(QCoreApplication.translate('BranchesNodes','Creating Branches and Nodes'))
        for enum,feature in enumerate(features):
            try:
                feedback.setProgress(int(enum*total))
                geom = feature.geometry().asPolyline()
                start,end = geom[0],geom[-1]
                startx,starty=start
                endx,endy=end
                branch = [(round(startx,P),round(starty,P)),(round(endx,P),round(endy,P))]    
                name = []      
                for (x,y) in branch:
                    if (x,y) in unknown_nodes:
                        V = 'U'
                    elif (x,y) in Graph:
                        node_count = Graph[(x,y)]
                        if node_count == 1:
                            V = 'I'
                        elif node_count == 3:
                            V = 'Y'
                        elif node_count == 4:
                            V = 'X'
                        else:
                            V = str(node_count)#'Error'
                            feedback.reportError(QCoreApplication.translate('Interpretation Boundary','Found intersection with %s nodes! Please repair fracture network using the repair tool and/or manual reinterpretation(s)'%(node_count)))
                    else:
                        V = 'Error'
                    name.append(V)
                Class = " - ".join(sorted(name[:2])) #Organize the order of names
                name = Class.replace('X','C').replace('Y','C')
                name = name.split(" - ")
                Connection = " - ".join(sorted(name))
                
                for m in cursorm:
                    geom = feature.geometry()
                    if geom.within(m[0]): #Branches
                        weight = 1
                        for (x,y) in branch:  #Points
                            testPoint = QgsGeometry.fromPointXY(QgsPointXY(x,y))
                            if not testPoint.within(m[0].buffer(-0.001,2)): #Test if point is on edge of sample area
                                V = 'E'
                                weight -= 0.5
                            elif (x,y) in unknown_nodes:
                                V = 'U'
                                weight -= 0.5
                            else:
                                if (x,y) in Graph:
                                    node_count = Graph[(x,y)]
                                    if node_count == 1:
                                        V = 'I'
                                    elif node_count == 3:
                                        V = 'Y'
                                    elif node_count == 4:
                                        V = 'X'
                                    else:
                                        V = str(node_count)#'Error'
                                else:
                                    V = 'Error'	
                            if m[1] in c_points:
                                if (x,y) not in c_points[m[1]]:
                                    data2 = [V,m[1]]
                                    c_points[m[1]].append((x,y))
                                    fet2.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x,y)))
                                    fet2.setAttributes(data2)
                                    writer2.addFeature(fet2,QgsFeatureSink.FastInsert) 
                            else:
                                data2 = [V,m[1]]
                                c_points[m[1]]=[(x,y)]
                                fet2.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x,y)))
                                fet2.setAttributes(data2)
                                writer2.addFeature(fet2,QgsFeatureSink.FastInsert)     
                        data = [Class,Connection,weight,m[1],feature.geometry().length()]
                        fet.setGeometry(feature.geometry())
                        fet.setAttributes(data)
                        writer.addFeature(fet,QgsFeatureSink.FastInsert)    
              
                    elif geom.intersects(m[0]):
                        
                        geom = geom.intersection(m[0])
                        parts = []
                        
                        if QgsWkbTypes.isSingleType(geom.wkbType()):
                            parts.append(geom)   
                        else:
                            for part in geom.parts():  #Check for multipart polyline
                                parts.append(QgsGeometry.fromPolyline(part)) #intersected geometry
                                
                        for inter in parts:
                            if inter.length() != 0.0: #Branches
                                geom = inter.asPolyline()
                                istart,iend = geom[0],geom[-1]
                                istartx,istarty=istart
                                iendx,iendy=iend
                                inter_branch = [(istartx,istarty),(iendx,iendy)]  
                                weight = 1
                                for (x,y) in inter_branch: #Points
                                    rx,ry = round(x,P),round(y,P)   
                                    V = 'E'     
                                    if (rx,ry) in unknown_nodes:
                                        V = 'U'
                                    elif (rx,ry) in Graph:
                                            node_count = Graph[(rx,ry)]
                                            if node_count == 1:
                                                V = 'I'
                                            elif node_count == 3:
                                                V = 'Y'
                                            elif node_count == 4:
                                                V = 'X'
                                            else:
                                                V = str(node_count)#'Error'
 
                                    if m[1] in c_points:
                                        if (rx,ry) not in c_points[m[1]]:
                                            data2 = [V,m[1]]
                                            c_points[m[1]].append((rx,ry))
                                            fet2.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x,y)))
                                            fet2.setAttributes(data2)
                                            writer2.addFeature(fet2,QgsFeatureSink.FastInsert) 
                                    else:
                                        c_points[m[1]]=[(rx,ry)]
                                        data2 = [V,m[1]]
                                        fet2.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x,y)))
                                        fet2.setAttributes(data2)
                                        writer2.addFeature(fet2,QgsFeatureSink.FastInsert) 
                                    if V == 'E' or V == 'U':
                                        weight -= 0.5
                                
                                data = [Class,Connection,weight,m[1],feature.geometry().length()]  
                                fet.setGeometry(inter)
                                fet.setAttributes(data)
                                writer.addFeature(fet,QgsFeatureSink.FastInsert)          

            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Sample Area','%s'%(e)))

        return {self.Branches:dest_id,self.Nodes:dest_id2}
