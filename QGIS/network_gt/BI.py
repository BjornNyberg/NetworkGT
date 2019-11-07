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

class IBlocks(QgsProcessingAlgorithm):

    Network = 'Fracture Network'
    Blocks = 'Blocks'
    Samples = 'Sample Area'
    
    def __init__(self):
        super().__init__()
        
    def name(self):
        return "Identify Blocks"

    def tr(self, text):
        return QCoreApplication.translate("Identify Blocks", text)

    def displayName(self):
        return self.tr("Identify Blocks")
 
    def group(self):
        return self.tr("Topology")
    
    def shortHelpString(self):
        return self.tr("Define Clusters of a Fracture Network")

    def groupId(self):
        return "Topology"
    
    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/blob/master/QGIS/README.pdf"
    
    def createInstance(self):
        return type(self)()

    def icon(self):
        pluginPath = os.path.join(os.path.dirname(__file__),'icons')
        return QIcon( os.path.join( pluginPath, 'IB.jpg') )
    
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Fracture Network"),
            [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Samples,
            self.tr("Samples"),
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.Blocks,
            self.tr("Identified Blocks"),
            QgsProcessing.TypeVectorPolygon))
    
    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsLayer(parameters, self.Samples, context)
        Network = self.parameterAsLayer(parameters, self.Network, context)

        fs = QgsFields()
        fs.append(QgsField('FID', QVariant.Int))
        fs.append(QgsField('Area', QVariant.Double))
        
        (writer, dest_id) = self.parameterAsSink(parameters, self.Blocks, context,
                                            fs, QgsWkbTypes.Polygon, layer.sourceCrs())
        
        pr = layer.dataProvider()
        new_fields = ['MinB','MeanB','MaxB','SumB','NoB','NoIB']
        for field in new_fields:
            if layer.fields().indexFromName(field) == -1:            
                pr.addAttributes([QgsField(field, QVariant.Double)])
                
        layer.updateFields()
        
        R = layer.fields().indexFromName('Radius')
        
        params = {'INPUT':Network,'KEEP_FIELDS':False,'OUTPUT':'memory:'}
        
        bs = st.run("qgis:polygonize",params)
        
        features = bs['OUTPUT'].getFeatures()

        idxs = []
        for field in new_fields:
            idxs.append(layer.fields().indexFromName(field))
            
        cursorm = []
        
        fet = QgsFeature() 
        feedback.pushInfo(QCoreApplication.translate('Blocks','Defining Blocks'))
        for feature in features:
            geom = feature.geometry()                
            cursorm.append(geom)
            fet.setGeometry(geom)
            rows = [feature.id(),geom.area()]
            fet.setAttributes(rows)
            writer.addFeature(fet,QgsFeatureSink.FastInsert)
            
        total = 100.0/layer.featureCount()
        feedback.pushInfo(QCoreApplication.translate('Blocks','Calculating Statistics'))

        layer.startEditing()
        for enum,feature in enumerate(layer.getFeatures()):
            if total > 0:
                feedback.setProgress(int(enum*total))
            data, count = [], 0 
            for m in cursorm:
                if R > -1:
                    Radius = feature['Radius']
                    geom = feature.geometry().centroid().buffer(float(Radius),5)
                else:
                    geom = feature.geometry()
                if geom.intersects(m): #Block intersects sample area
                    if m.within(geom):
                        count += 1
                    intersect = geom.intersection(m)
                    data.append(intersect.area())
            if data:
                pr.changeAttributeValues({feature.id():{idxs[0]:float(np.min(data)),idxs[1]:float(np.mean(data)),idxs[2]:float(np.max(data)),idxs[3]:float(sum(data)),idxs[4]:float(len(data)),idxs[5]:float(len(data)-count)}})
        layer.commitChanges() 

        return {self.Blocks:dest_id}
                
