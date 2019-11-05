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
import numpy as np
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature, QgsPointXY, QgsProcessingParameterBoolean,QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsProcessingParameterNumber,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer)
from qgis.PyQt.QtGui import QIcon

class TBlocks(QgsProcessingAlgorithm):

    Clusters = 'Clusters'
    Nodes = 'Nodes'
    Samples = 'Sample Areas'
    
    def __init__(self):
        super().__init__()
        
    def name(self):
        return "Theoretical Blocks"

    def tr(self, text):
        return QCoreApplication.translate("Calculate Theoretical Blocks", text)

    def displayName(self):
        return self.tr("Theoretical Blocks")
 
    def group(self):
        return self.tr("Geometry")
    
    def shortHelpString(self):
        return self.tr("Define Theoretical Blocks of a Fracture Network")

    def groupId(self):
        return "Geometry"
    
    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/blob/master/QGIS/README.pdf"
    
    def createInstance(self):
        return type(self)()

    def icon(self):
        pluginPath = os.path.join(os.path.dirname(__file__),'icons')
        return QIcon( os.path.join( pluginPath, 'BA.jpg') )
    
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Samples,
            self.tr("Topology Parameters"),
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Clusters,
            self.tr("Clusters"),
            [QgsProcessing.TypeVectorLine]))
    
    def processAlgorithm(self, parameters, context, feedback):
        try:   
            layer = self.parameterAsLayer(parameters, self.Samples, context)
            layer2 = self.parameterAsLayer(parameters, self.Clusters, context)

            pr = layer.dataProvider()
            new_fields = ['NoWB','NoTB','TB_Avg']
            for field in new_fields:
                if layer.fields().indexFromName(field) == -1:            
                    pr.addAttributes([QgsField(field, QVariant.Double)])
            layer.updateFields() 
            T = layer.fields().indexFromName('Sample_No_')
            if T == -1:
                feedback.reportError(QCoreApplication.translate('Error','Topology Parameters dataset input is invalid - requires a Sample_No_ field'))
                return {}
            
            T = layer2.fields().indexFromName('Weight')
            T2 = layer2.fields().indexFromName('Cluster')
            if T == -1 or T2 == -1:
                feedback.reportError(QCoreApplication.translate('Error','Cluster input is invalid - Run Clustering tool prior to Block Analysis tool'))
                return {}

            clusters = {}
            
            total = 100.0/layer2.featureCount()
            feedback.pushInfo(QCoreApplication.translate('Blocks','Reading Cluster Data'))
            for enum,feature in enumerate(layer2.getFeatures()):
                if total > 0:
                    feedback.setProgress(int(enum*total))
                ID = feature['Sample_No_']
                CL = feature['Cluster']
                if ID not in clusters:
                    if feature['Weight'] == 0.5:
                        clusters[ID] = {CL:1}
                    else:
                        clusters[ID] = {CL:0}
                else:
                    cluster = clusters[ID]
                    if CL not in cluster:
                        if feature['Weight'] == 0.5:
                            cluster[CL] = 1
                        else:
                            cluster[CL] = 0
                    else:
                        value = cluster[CL]
                        if value != 0 and feature['Weight'] == 0.5:
                            cluster[CL] = 1
                    clusters[ID] = cluster

            total = 100.0/layer.featureCount()
            feedback.pushInfo(QCoreApplication.translate('Blocks','Calculating Theoretical Blocks'))
            f_len = len(layer.fields())
            layer.startEditing()
            for enum,feature in enumerate(layer.getFeatures()):
                if total > 0:
                    feedback.setProgress(int(enum*total))
                ID = feature['Sample_No_']
                if ID in clusters:
                    num_n = feature['No. Nodes'] 
                    num_en = feature['E']

                    num_b = feature['C - C'] + feature['I - I'] + feature['C - I']

                    num_c = len(clusters[ID])
                    num_ic = sum(clusters[ID].values())
                    Area = feature['Area']
                                 
                    blocks = num_b - num_n + num_c

                    if num_ic > 0:
                        tb = ((num_en - num_ic + 1) / 2.0) + blocks
                    else:
                        tb = 0

                    pr.changeAttributeValues({feature.id():{f_len-3:float(blocks),f_len-2:float(tb),f_len-1:float(tb/Area)}})
            layer.commitChanges() 

        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            return {}
        return {}
                
