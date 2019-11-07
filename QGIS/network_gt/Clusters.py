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
import numpy as np
import networkx as nx
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature, QgsPointXY, QgsProcessingParameterBoolean,QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsProcessingParameterNumber,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer)
from qgis.PyQt.QtGui import QIcon

class Clusters(QgsProcessingAlgorithm):

    Network = 'Fracture Network'
    stats = 'Calculate Statistics'
    
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
        
        self.addParameter(QgsProcessingParameterBoolean(self.stats,
                self.tr("Calculate Statistics"),False))
    
    def processAlgorithm(self, parameters, context, feedback):
         
        Network = self.parameterAsLayer(parameters, self.Network, context)

        S = parameters[self.stats]
        pr = Network.dataProvider()

        field_check = Network.fields().indexFromName('Sample_No_')
        field_check2 = Network.fields().indexFromName('Connection')
        
        if Network.fields().indexFromName('Cluster') == -1:            
            pr.addAttributes([QgsField('Cluster', QVariant.Int)])
            
        if S:
            if field_check2 != -1:
                fnames =  ['C - C','C - I','I - I','C - U','C - I','U - U','Clus']
            else:
                fnames = ['Clus']
            dataV = {}
            idxs = {}
            
            stats = ['sum','count']    
            for k in fnames:
                for s in stats:
                    field = '%s %s'%(s,k)
                    if Network.fields().indexFromName(field) == -1:
                        pr.addAttributes([QgsField(field, QVariant.Double)])
                    
            Network.updateFields()
            
            for k in fnames:
                for s in stats:
                    field = '%s %s'%(s,k)
                    idxs[field] = Network.fields().indexFromName(field)
        else:
            Network.updateFields()

        idx = Network.fields().indexFromName('Cluster')
          
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
               
        Network.startEditing()  
        feedback.pushInfo(QCoreApplication.translate('Clusters','Updating Feature Class'))
        for enum,feature in enumerate(Network.getFeatures()):
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
                
                branch = ((startx,starty),(endx,endy)) + (ID,)

                if branch not in clusters:
                    branch = ((endx,endy),(startx,starty)) + (ID,)
                try:
                    cluster = clusters[branch]
                except Exception:
                    cluster = -1

                rows = {idx:cluster}
                pr.changeAttributeValues({feature.id():rows})
                if S and cluster != -1:
                    if field_check2 != -1:
                        C = feature['Connection']
                        names = {'C - C':[],'C - I':[],'I - I':[],'C - U':[],'C - I':[],'U - U':[]}
                    else:
                        C = 'Clus'
                        names = {'Clus':[]}

                    if cluster not in dataV:
                        dataV[cluster] = names
                          
                    values = dataV[cluster]
                    values[C].append(feature.geometry().length())
                    
                    dataV[cluster] = values
            except Exception:
                continue
                
        Network.commitChanges()
        
        if S:
            Network.startEditing()
            feedback.pushInfo(QCoreApplication.translate('Clusters','Updating Statistics'))

            for enum,feature in enumerate(Network.getFeatures()):
                try:
                    if total > 0:
                        feedback.setProgress(int(enum*total))
                        
                    cluster = feature['Cluster']
                    clusterV = dataV[cluster]
                    
                    rows = {}
                    for k in fnames: 
                        for s in stats:
                            field = '%s %s'%(s,k)
                            idx = idxs[field]
                            
                            if k not in clusterV:
                                values = [val for sublist in list(clusterV.values()) for val in sublist]
                            else:
                                values = clusterV[k]
                                
                            if s == 'count':
                                rows[idx] = float(np.size(values))
                            elif s == 'min':
                                rows[idx] = float(np.min(values))
                            elif s == 'mean':
                                rows[idx] = float(np.mean(values))
                            elif s == 'max':
                                rows[idx] = float(np.max(values))
                            elif s == 'sum':
                                rows[idx] = float(np.sum(values))
                        
                    pr.changeAttributeValues({feature.id():rows})
                    
                except Exception:
                    continue
            Network.commitChanges()
        
        return {}
                
