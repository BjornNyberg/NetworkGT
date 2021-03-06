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

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature, QgsPointXY, QgsProcessingParameterString, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsProcessingParameterNumber,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer)
from qgis.PyQt.QtGui import QIcon

import os

class Sets(QgsProcessingAlgorithm):

    Network = 'Network'
    Sets='Sets'
    Bin_V ='Bins'
    Output = 'Output'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Define Sets"

    def tr(self, text):
        return QCoreApplication.translate("Sets", text)

    def displayName(self):
        return self.tr("Define Sets")

    def group(self):
        return self.tr("3. Geometry")

    def shortHelpString(self):
        return self.tr("Groups fracture lines into sets detemrined by user defined orientation bins. Orientaiton bins must be defiend from 0 to 180 using a notation whereby each bin is defined by an orientation range within a pair of brackets, e.g. (30,90),(90,150),(150,30). Alternatively the user can specify an equal interval bin size. \n The input needs to be a fracture network linestring and the orientation, set number and fracture length are added to the attribute table once calculated.\n Please refer to the help button for more information.")

    def groupId(self):
        return "3. Geometry"

    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/wiki/3.-Geometry-Analysis"

    def createInstance(self):
        return type(self)()

    def icon(self):
        n,path = 2,os.path.dirname(__file__)
        while(n):
            path=os.path.dirname(path)
            n -=1
        pluginPath = os.path.join(path,'icons')
        return QIcon( os.path.join( pluginPath, 'Sets.jpg') )

    def initAlgorithm(self, config):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Fracture Network"),
            [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterString(
            self.Sets,
            self.tr("Set Definitions"),
            '(0,90),(90,180)'))
        self.addParameter(QgsProcessingParameterNumber(
            self.Bin_V,
            self.tr("Set Definitions By Bin Size"),
            QgsProcessingParameterNumber.Double,
            0.0,minValue=0.0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.Output,
            self.tr("Output"),
            QgsProcessing.TypeVectorLine, '',optional=True))

    def processAlgorithm(self, parameters, context, feedback):

        try:
            import math
            import numpy as np
        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            feedback.reportError(QCoreApplication.translate('Error',' '))
            feedback.reportError(QCoreApplication.translate('Error','Error loading modules - please install the necessary dependencies'))
            return {}

        layer = self.parameterAsLayer(parameters, self.Network, context)
        bin_v =  parameters[self.Bin_V]
        if bin_v > 0:
            x = np.arange(0,180,bin_v)
            y = np.arange(bin_v,180+bin_v,bin_v)
            y[-1] = 180
            bins = tuple(zip(x,y))
        else:
            bins = list(eval(self.parameterAsString(parameters, self.Sets, context)))

        new_fields = ['Set', 'Orient', 'Length']

        if self.Output in parameters:
            fields = QgsFields()
            for field in layer.fields():
                if field.name() not in new_fields:
                    fields.append(QgsField(field.name(), field.type()))

            for field in new_fields:
                fields.append(QgsField(field, QVariant.Double))

            (writer, dest_id) = self.parameterAsSink(parameters, self.Output, context,
                                                     fields, QgsWkbTypes.LineString, layer.sourceCrs())
            fet = QgsFeature()

        else:
            pr = layer.dataProvider()

            for field in new_fields:
                if layer.fields().indexFromName(field) == -1:
                    pr.addAttributes([QgsField(field, QVariant.Double)])

            layer.updateFields()
            idxs = []
            for field in new_fields:
                idxs.append(layer.fields().indexFromName(field))

            layer.startEditing()

        features = layer.selectedFeatures()
        total = layer.selectedFeatureCount()
        if len(features) == 0:
            features = layer.getFeatures()
            total = layer.featureCount()

        total = 100.0/total

        for enum,feature in enumerate(features):
            if total > 0:
                feedback.setProgress(int(enum*total))
            geom = feature.geometry()
            if QgsWkbTypes.isSingleType(geom.wkbType()):
                geom = [geom.asPolyline()]
            else:
                geom = geom.asMultiPolyline()

            if len(geom) == 0:
                feedback.reportError(QCoreApplication.translate('Error','Warning - skipping null geometry linestring.'))
                continue

            x, y = 0, 0
            for part in geom:
                startx = None
                for point in part:
                    if startx == None:
                        startx, starty = point
                        continue
                    endx, endy = point

                    dx = endx - startx
                    dy = endy - starty

                    l = math.sqrt((dx ** 2) + (dy ** 2))
                    angle = math.degrees(math.atan2(dy, dx))
                    x += math.cos(math.radians(angle)) * l
                    y += math.sin(math.radians(angle)) * l

                    startx, starty = endx, endy

            mean = 90 - np.around(math.degrees(math.atan2(y, x)), decimals=4)
            if mean > 180:
                mean -= 180
            elif mean < 0:
                mean += 180

            value = -1
            for enum, b in enumerate(bins):
                if float(b[0]) > float(b[1]):
                    if mean >= float(b[0]) or mean <= float(b[1]):
                        value = enum
                        break
                elif mean >= float(b[0]) and mean <= float(b[1]):
                    value = enum
                    break

            if self.Output in parameters:
                rows = []
                for field in layer.fields():
                    if field.name() not in new_fields:
                        rows.append(feature[field.name()])
                rows.extend([value,float(mean),float(feature.geometry().length())])

                fet.setGeometry(feature.geometry())
                fet.setAttributes(rows)
                writer.addFeature(fet, QgsFeatureSink.FastInsert)
            else:
                rows = {idxs[0]:value,idxs[1]:float(mean),idxs[2]:float(feature.geometry().length())}
                pr.changeAttributeValues({feature.id():rows})

        if self.Output in parameters:
            return {self.Output: dest_id}
        else:
            layer.commitChanges()
            return {}
