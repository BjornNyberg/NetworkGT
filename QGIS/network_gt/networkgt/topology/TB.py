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
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature, QgsPointXY, QgsProcessingParameterBoolean,QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsProcessingParameterNumber,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer)
from qgis.PyQt.QtGui import QIcon

class TBlocks(QgsProcessingAlgorithm):

    Clusters = 'Clusters'
    Nodes = 'Nodes'
    Samples = 'Sample Areas'
    Output = 'Output'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Theoretical Blocks"

    def tr(self, text):
        return QCoreApplication.translate("Calculate Theoretical Blocks", text)

    def displayName(self):
        return self.tr("Theoretical Blocks")

    def group(self):
        return self.tr("4. Topology")

    def shortHelpString(self):
        return self.tr("Uses topological information to calculates the theoretical number of blocks within a specified sample area.  The tool provides an estimate of both the number of whole blocks within a sample area as well as the number of half-blocks that leave the sample area. The calculation is derived from a generalisation of Euler's formula whereby the number of nodes (N), branches (B), clusters (K) and blocks (R) relate to one another by: R = B - N + K (See Nyberg et al., 2018, Geosphere for a description of the calculation used in NetworkGT). \n The input is a Branches linestring with identified clusters in its attribute table and an associated Topological Paramaters polygon/contour grid. The output adds the results of the calculation to the Topology Parameters polygon/contour grid.\n Please refer to the help button for more information.")

    def groupId(self):
        return "4. Topology"

    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/wiki/4.-Topology-Analysis"

    def createInstance(self):
        return type(self)()

    def icon(self):
        n,path = 2,os.path.dirname(__file__)
        while(n):
            path=os.path.dirname(path)
            n -=1
        pluginPath = os.path.join(path,'icons')
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
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.Output,
            self.tr("Output"),
            QgsProcessing.TypeVectorPolygon,'',optional=True))

    def processAlgorithm(self, parameters, context, feedback):
        try:
            layer = self.parameterAsLayer(parameters, self.Samples, context)
            layer2 = self.parameterAsLayer(parameters, self.Clusters, context)

            new_fields = ['NoWB','NoTB','TB_Avg']

            if self.Output in parameters:
                fields = QgsFields()
                for field in layer.fields():
                    if field.name() not in new_fields:
                        fields.append(QgsField(field.name(), field.type()))
                for field in new_fields:
                    fields.append(QgsField(field, QVariant.Double))
                (writer, dest_id) = self.parameterAsSink(parameters, self.Output, context,
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

            T = layer.fields().indexFromName('Sample_No_')
            if T == -1:
                feedback.reportError(QCoreApplication.translate('Error','Topology Parameters dataset input is invalid - requires a Sample_No_ field'))
                return {}

            T = layer2.fields().indexFromName('Weight')
            T2 = layer2.fields().indexFromName('Cluster')
            if T == -1 or T2 == -1:
                feedback.reportError(QCoreApplication.translate('Error','Cluster input is invalid - Run Clustering tool prior to Block Analysis tool'))
                return {}

            iclusters = {}
            clusters = {}

            total = 100.0/layer2.featureCount()
            feedback.pushInfo(QCoreApplication.translate('Blocks','Reading Cluster Data'))
            for enum,feature in enumerate(layer2.getFeatures()):
                if total > 0:
                    feedback.setProgress(int(enum*total))
                ID = feature['Sample_No_']
                CL = feature['Cluster']
                if ID not in clusters:
                    clusters[ID] = []
                    iclusters[ID] = {}

                cluster = clusters[ID]
                if CL not in cluster:
                    cluster.append(CL)

                icluster = iclusters[ID]
                if CL not in icluster:
                    if feature['Weight'] != 1:
                        icluster[CL] = 1

                clusters[ID] = cluster
                iclusters[ID] = icluster

            total = 100.0/layer.featureCount()
            feedback.pushInfo(QCoreApplication.translate('Blocks','Calculating Theoretical Blocks'))
            if self.Output in parameters:
                fet = QgsFeature()
            else:
                layer.startEditing()
            for enum,feature in enumerate(layer.getFeatures()):
                if total > 0:
                    feedback.setProgress(int(enum*total))
                ID = feature['Sample_No_']
                if ID in clusters:
                    num_n = feature['No. Nodes']
                    num_en = feature['E']

                    num_b = (feature['X']*4 + feature['Y']*3 + feature['I'] + feature['U'] + num_en)/2.0

                    num_c = len(clusters[ID])
                    num_ic = sum(iclusters[ID].values())

                    Area = feature['Area']

                    blocks = num_b - (num_n + num_en) + num_c

                    tbArea = 0
                    if num_ic > 0:

                        tb = ((num_en - num_ic + 1) / 2.0) + blocks
                        if tb > 0:
                            tbArea = Area/tb
                    else:
                        tb = 0

                if self.Output in parameters:

                    rows = []
                    for field in layer.fields():
                        if field.name() not in new_fields:
                            rows.append(feature[field.name()])
                    rows.extend([float(blocks),float(tb),tbArea])

                    fet.setGeometry(feature.geometry())
                    fet.setAttributes(rows)
                    writer.addFeature(fet, QgsFeatureSink.FastInsert)
                else:
                    pr.changeAttributeValues({feature.id():{idxs[0]:float(blocks),idxs[1]:float(tb),idxs[2]:tbArea}})

        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            return {}
        if self.Output in parameters:
            return {self.Output: dest_id}
        else:
            layer.commitChanges()
            return {}
