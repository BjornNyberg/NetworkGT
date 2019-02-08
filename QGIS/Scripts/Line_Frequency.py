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
from qgis.core import (QgsField, QgsFeature, QgsPointXY, QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsProcessingParameterNumber,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer)
from qgis.utils import iface

class Line_Frequency(QgsProcessingAlgorithm):

    LG = 'Line Grid'
    Network = 'Fracture Network'
    LFD='Line Frequency Data'
    LFS ='Line Frequency Stats'
    
    def __init__(self):
        super().__init__()
        
    def name(self):
        return "Line Frequency"

    def tr(self, text):
        return QCoreApplication.translate("Line_Grid", text)

    def displayName(self):
        return self.tr("Line Frequency")
 
    def group(self):
        return self.tr("NetworkGT")
    
    def shortHelpString(self):
        return self.tr("Create a Line Frequency sampling method")

    def groupId(self):
        return "Topology"
    
    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT"
    
    def createInstance(self):
        return type(self)()
    
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.LG,
            self.tr("Line Grid"),
            [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Fracture Network"),
            [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.LFD,
            self.tr("Line Frequency Data"),
            QgsProcessing.TypeVectorLine))
        #self.addParameter(QgsProcessingParameterFeatureSink(
         #   self.LFS,
          #  self.tr("Line Frequency Stats"),
           # QgsProecessing.TypeVectorLine))
    
    def processAlgorithm(self, parameters, context, feedback):
        
        LG = self.parameterAsSource(parameters, self.LG, context)
        Network = self.parameterAsSource(parameters, self.Network, context)
        
        infc = parameters[self.LG]
        infc2 = parameters[self.Network]
        
        field_check = LG.fields().indexFromName('Sample_No_')
            
        if field_check == -1:            
            feedback.reportError(QCoreApplication.translate('Input Error','Add "Sample_No_" attribute field to Line Grid input file'))
            return {}
            
        fs = QgsFields()
        fs.append(QgsField('Sample_No_', QVariant.Int))
        fs.append(QgsField('Count', QVariant.Int))
        fs.append(QgsField('Distance', QVariant.Double))  
        
        (writer, dest_id) = self.parameterAsSink(parameters, self.LFD, context,
                                            fs, QgsWkbTypes.LineString, Network.sourceCrs())
        sources,edges,Lengths,k = {},{},{},{}
        for feature in LG.getFeatures(QgsFeatureRequest()):
            geom = feature.geometry()
            if QgsWkbTypes.isSingleType(geom.wkbType()):
                geom = geom.asPolyline()
            else:
                geom = geom.asMultiPolyline()[0]
            x,y = geom[0]
            startx,starty=round(x,6), round(y,6)
            sources[feature['Sample_No_']] = (startx,starty)
        
        feedback.pushInfo(QCoreApplication.translate('TempFiles','Creating Line Frequency Sampling'))
        parameters = {'INPUT':infc,'LINES':infc2,'OUTPUT':'memory:'}  
        templines = st.run('native:splitwithlines',parameters,context=context,feedback=feedback)   
        
        for feature in templines['OUTPUT'].getFeatures(QgsFeatureRequest()):
            geom = feature.geometry()
            if QgsWkbTypes.isSingleType(geom.wkbType()):
                geom = geom.asPolyline()
            else:
                geom = geom.asMultiPolyline()[0]
            start,end = geom[0],geom[-1]
            startx,starty=start
            endx,endy=end

            pnts1,pnts2 = [(round(startx,6),round(starty,6)),(round(endx,6),round(endy,6))]     
            Length = feature.geometry().length()
            ID = feature['Sample_No_']

            if ID in edges:
                edges[ID].add_edge(pnts1,pnts2,weight=Length)
            else:
                G = nx.Graph()
                G.add_edge(pnts1,pnts2,weight=Length)
                edges[ID] = G
        
        fet = QgsFeature() 
        for feature in templines['OUTPUT'].getFeatures(QgsFeatureRequest()):
            geom = feature.geometry()
            if QgsWkbTypes.isSingleType(geom.wkbType()):
                geom = geom.asPolyline()
            else:
                geom = geom.asMultiPolyline()[0]
            start,end = geom[0],geom[-1]
            startx,starty=start
            endx,endy=end

            startx,starty = (round(startx,6),round(starty,6))
            endx, endy = (round(endx,6),round(endy,6))  
            
            ID = feature['Sample_No_']

            if ID not in Lengths:
                G = edges[ID]
                if len(G.nodes()) > 2:
                    source = sources[ID]
                    length,path = nx.single_source_dijkstra(G,source,weight='weight')
                    Lengths[ID] = length
                    k[ID] = list(length.keys())
            c, L = -1,-1
            if ID in Lengths:
                try:
                    c = k[ID].index((endx,endy))
                    L = Lengths[ID][(endx,endy)]
                except Exception as e:
                    pass
                fet.setGeometry(feature.geometry())
                fet.setAttributes([ID,c,L])
                writer.addFeature(fet,QgsFeatureSink.FastInsert)    
        del sources,edges,Lengths,k

        return {self.LFD:dest_id}
