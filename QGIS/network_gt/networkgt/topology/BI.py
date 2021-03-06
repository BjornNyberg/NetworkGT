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

import os
import processing as st
import numpy as np
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature, QgsPointXY, QgsProcessingParameterBoolean,QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsProcessingParameterNumber,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer)
from qgis.PyQt.QtGui import QIcon

class IBlocks(QgsProcessingAlgorithm):

    Network = 'Fracture Network'
    Blocks = 'Blocks'
    Samples = 'Sample Area'
    Output = 'Output'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Identify Blocks"

    def tr(self, text):
        return QCoreApplication.translate("Identify Blocks", text)

    def displayName(self):
        return self.tr("Identify Blocks")

    def group(self):
        return self.tr("4. Topology")

    def shortHelpString(self):
        return self.tr("Identifies and extracts the blocks enclosed by fracture lines within a sepcified sample area. \n The input is a fracture network/branches linestring and a sample area polygon/contour grid . The output is an  polygon feature containing all idnetifed blocks. In additon a range of statistic fields on block sizes (e.g. maximum, minium, mean etc.) are added to the sample area polygon/contour grid.\n Please refer to the help button for more information.")

    def groupId(self):
        return "4. Topology"

    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/wiki/4.-Topology"

    def createInstance(self):
        return type(self)()

    def icon(self):
        n,path = 2,os.path.dirname(__file__)
        while(n):
            path=os.path.dirname(path)
            n -=1
        pluginPath = os.path.join(path,'icons')
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
            QgsProcessing.TypeVectorPolygon,'',optional=True))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.Output,
            self.tr("Output"),
            QgsProcessing.TypeVectorPolygon,'',optional=True))

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsLayer(parameters, self.Samples, context)
        Network = self.parameterAsLayer(parameters, self.Network, context)

        if self.Blocks in parameters:
            fs = QgsFields()
            fs.append(QgsField('FID', QVariant.Int))
            fs.append(QgsField('Area', QVariant.Double))

            (writer, dest_id) = self.parameterAsSink(parameters, self.Blocks, context,
                                                fs, QgsWkbTypes.Polygon, layer.sourceCrs())
        pr = Network.dataProvider()

        field_check = Network.fields().indexFromName('Sample_No_')
        field_check2 = Network.fields().indexFromName('Connection')

        if Network.fields().indexFromName('Cluster') == -1:
            pr.addAttributes([QgsField('Cluster', QVariant.Int)])
            Network.updateFields()

        idx = Network.fields().indexFromName('Cluster')
        new_fields = ['MinB', 'MeanB', 'MaxB', 'SumB', 'NoB', 'NoIB']

        if self.Output in parameters:
            fields = QgsFields()
            for field in layer.fields():
                if field.name() not in new_fields:
                    fields.append(QgsField(field.name(), field.type()))
            for field in new_fields:
                fields.append(QgsField(field, QVariant.Double))

            (writer, dest_id2) = self.parameterAsSink(parameters, self.Output, context,
                                                     fields, QgsWkbTypes.Polygon, layer.sourceCrs())
        else:
            pr = layer.dataProvider()

            for field in new_fields:
                if layer.fields().indexFromName(field) == -1:
                    pr.addAttributes([QgsField(field, QVariant.Double)])

            layer.updateFields()

            idxs = []
            for field in new_fields:
                idxs.append(layer.fields().indexFromName(field))

        R = layer.fields().indexFromName('Radius')

        params = {'INPUT': Network,'START_DISTANCE':0.0001,'END_DISTANCE':0.0001,'OUTPUT':'memory:'}
        extend = st.run("native:extendlines",params,context=context,feedback=feedback )

        params = {'INPUT':extend['OUTPUT'],'KEEP_FIELDS':False,'OUTPUT':'memory:'}

        bs = st.run("qgis:polygonize",params,context=context,feedback=feedback)

        features = bs['OUTPUT'].getFeatures()

        cursorm = []

        fet = QgsFeature()
        feedback.pushInfo(QCoreApplication.translate('Blocks','Defining Blocks'))
        for feature in features:
            geom = feature.geometry()
            cursorm.append(geom)
            if self.Blocks in parameters:
                fet.setGeometry(geom)
                rows = [feature.id(),geom.area()]
                fet.setAttributes(rows)
                writer.addFeature(fet,QgsFeatureSink.FastInsert)

        total = 100.0/layer.featureCount()
        feedback.pushInfo(QCoreApplication.translate('Blocks','Calculating Statistics'))

        if self.Output in parameters:
            fet2 = QgsFeature()
        else:
            layer.startEditing()

        for enum,feature in enumerate(layer.getFeatures()):
            if total > 0:
                feedback.setProgress(int(enum*total))
            data, count = [], 0
            for m in cursorm:
                if R > -1:
                    Radius = feature['Radius']
                    geom = feature.geometry().centroid().buffer(float(Radius),100)
                else:
                    geom = feature.geometry()
                if geom.intersects(m): #Block intersects sample area
                    if m.within(geom):
                        count += 1
                    intersect = geom.intersection(m)
                    data.append(intersect.area())
            if self.Output in parameters:
                rows = []
                for field in layer.fields():
                    if field.name() not in new_fields:
                        rows.append(feature[field.name()])
                if data:
                    rows.extend([float(np.min(data)),float(np.mean(data)),float(np.max(data)),float(sum(data)),float(len(data)),float(len(data)-count)])
                else:
                    rows.extend([0,0,0,0,0,0])

                fet2.setGeometry(feature.geometry())
                fet2.setAttributes(rows)
                writer.addFeature(fet2, QgsFeatureSink.FastInsert)
            else:
                if data:
                    pr.changeAttributeValues({feature.id():{idxs[0]:float(np.min(data)),idxs[1]:float(np.mean(data)),idxs[2]:float(np.max(data)),idxs[3]:float(sum(data)),idxs[4]:float(len(data)),idxs[5]:float(len(data)-count)}})
                else:
                    pr.changeAttributeValues({feature.id():{idxs[0]:0,idxs[1]:0,idxs[2]:0,idxs[3]:0,idxs[4]:0,idxs[5]:0}})

        if self.Output in parameters:
            if self.Blocks in parameters:
                return {self.Blocks: dest_id, self.Output: dest_id2}
            else:
                return {self.Output: dest_id2}
        else:
            layer.commitChanges()
            if self.Blocks in parameters:
                return {self.Blocks:dest_id}
