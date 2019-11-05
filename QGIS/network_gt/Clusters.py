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
    
import os, sys, math
import processing as st
import pandas as pd
import networkx as nx
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature, QgsPointXY, QgsProcessingParameterBoolean,QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsProcessingParameterNumber,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer)
from qgis.PyQt.QtGui import QIcon

class Clusters(QgsProcessingAlgorithm):

    Clusters = 'Clusters'
    Network = 'Fracture Network'
    SplitCs = 'Split Clusters'
    
    def __init__(self):
        super().__init__()
        
    def name(self):
        return "Clusters"

    def tr(self, text):
        return QCoreApplication.translate("Define Clusters", text)

    def displayName(self):
        return self.tr("Define Clusters")
 
    def group(self):
        return self.tr("Geometry")
    
    def shortHelpString(self):
        return self.tr("Define Clusters of a Fracture Network")

    def groupId(self):
        return "Geometry"
    
    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/blob/master/QGIS/README.pdf"
    
    def createInstance(self):
        return type(self)()

    def icon(self):
        pluginPath = os.path.join(os.path.dirname(__file__),'icons')
        return QIcon( os.path.join( pluginPath, 'CL.jpg') )
    
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Fracture Network"),
            [QgsProcessing.TypeVectorLine]))
    
    def processAlgorithm(self, parameters, context, feedback):
         
        Network = self.parameterAsLayer(parameters, self.Network, context)
        
        pr = Network.dataProvider()

        if Network.fields().indexFromName('Cluster') == -1:            
            pr.addAttributes([QgsField('Cluster', QVariant.Int)])
            Network.updateFields() 
        idx = Network.fields().indexFromName('Cluster')
        
        field_check = Network.fields().indexFromName('Sample_No_')
            
        Precision = 6
        graphs = {}
        total = 100.0/Network.featureCount()
        
        feedback.pushInfo(QCoreApplication.translate('Cluster','Building Graph'))
        for enum,feature in enumerate(Network.getFeatures()): #Build Graph
            try:
                if total > 0:
                    feedback.setProgress(int(enum*total))
                    
                if field_check != -1:
                    ID = feature['Sample_No_']
                else:
                    ID = 1
 
                geom = feature.geometry()
                if geom.isMultipart():
                    data = geom.asMultiPolyline()[0]
                else:
                    data = geom.asPolyline()
                    
                start,end = data[0],data[-1]

                startx,starty = (round(start.x(),Precision),round(start.y(),Precision))
                endx,endy = (round(end.x(),Precision),round(end.y(),Precision))
                
                if ID not in graphs:
                    Graph = nx.Graph()
                    graphs[ID] = Graph
                    
                graphs[ID].add_edge((startx,starty),(endx,endy))
                
            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))

        feedback.pushInfo(QCoreApplication.translate('Clusters','Calculating Clusters'))
        Network.startEditing()   
        clusters = {}
        c = 0
        total2 = 100.0/len(graphs)
        for enum,FID in enumerate(graphs):
            feedback.setProgress(int(enum*total2))
            G = graphs[FID]
            for graph in nx.connected_components(G):
                c+=1

                G2 = G.subgraph(graph).copy() 
                
                for edge in G2.edges():
                    data = edge + (FID,)
                    clusters[data] = c
        
        feedback.pushInfo(QCoreApplication.translate('Clusters','Updating Feature Class'))
        for enum,feature in enumerate(Network.getFeatures()):
            if total > 0:
                feedback.setProgress(int(enum*total))
                
            if field_check != -1:
                ID = feature['Sample_No_']
            else:
                ID = 1
                
            geom = feature.geometry()
            if geom.isMultipart():
                data = geom.asMultiPolyline()[0]
            else:
                data = geom.asPolyline()
                    
            start,end = data[0],data[-1]

            startx,starty = (round(start.x(),Precision),round(start.y(),Precision))
            endx,endy = (round(end.x(),Precision),round(end.y(),Precision))
            
            branch = ((startx,starty),(endx,endy)) + (ID,)

            if branch not in clusters:
                branch = ((endx,endy),(startx,starty)) + (ID,)
                
            cluster = clusters[branch]
            rows = {idx:cluster}
            pr.changeAttributeValues({feature.id():rows}) 
        Network.commitChanges() 
        return {}
                
