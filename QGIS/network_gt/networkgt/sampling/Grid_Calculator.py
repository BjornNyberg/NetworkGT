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
from qgis.core import (edit,QgsField, QgsFeature,QgsProcessingParameterEnum, QgsProcessingParameterBoolean, QgsPointXY, QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsProcessingParameterNumber,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer)
from qgis.PyQt.QtGui import QIcon

class GridCalc(QgsProcessingAlgorithm):

    Grid='Grid'
    Grid2 = 'Grid2'
    outGrid = 'outGrid'
    Stats = 'stats'
    absolute = 'abs'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Grid Calculator"

    def tr(self, text):
        return QCoreApplication.translate("Simple_Grid", text)

    def displayName(self):
        return self.tr("Grid Calculator")

    def group(self):
        return self.tr("2. Sampling")

    def shortHelpString(self):
        return self.tr("A simple method to calculate values between two contour grids.")

    def groupId(self):
        return "2. Sampling"

    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/wiki/2.-Sampling-Methods"

    def createInstance(self):
        return type(self)()

  #  def icon(self):
  #      n,path = 2,os.path.dirname(__file__)
  #      while(n):
  #          path=os.path.dirname(path)
  #          n -=1
  #      pluginPath = os.path.join(path,'icons')
  #      return QIcon( os.path.join( pluginPath, 'CG.jpg') )

    def initAlgorithm(self, config):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Grid,
            self.tr("Contour Grid 1"),
            [QgsProcessing.TypeVectorPolygon]))

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Grid2,
            self.tr("Contour Grid 2"),
            [QgsProcessing.TypeVectorPolygon]))

        self.addParameter(QgsProcessingParameterEnum(self.Stats,
                                                     self.tr('Method'), options=[self.tr("add"),self.tr("subtract"),self.tr("multiply"),self.tr("divide")],
                                                     defaultValue=0))
        self.addParameter(QgsProcessingParameterBoolean(self.absolute,
                                                        self.tr("Absolute Value"), False))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.outGrid,
            self.tr("Contour Grid"),
            QgsProcessing.TypeVectorPolygon))

    def processAlgorithm(self, parameters, context, feedback):

        Grid = self.parameterAsVectorLayer(parameters, self.Grid, context)
        Grid2 = self.parameterAsVectorLayer(parameters, self.Grid2, context)
        stat = self.parameterAsInt(parameters, self.Stats, context)
        absolute = parameters[self.absolute]

        if Grid.fields().indexFromName('Sample_No_') == -1 or Grid2.fields().indexFromName('Sample_No_') == -1:
            feedback.reportError(QCoreApplication.translate('Error','Contour grid input is invalid - requires a sample no ID.'))
            return {}
    
        fs = QgsFields()
        fs.append(QgsField("Sample_No_", QVariant.Int))
        names =  []
        for field in Grid.fields():
            if field.type() == QVariant.Double:
                fs.append(QgsField(field.name(), QVariant.Double))
                names.append(field.name())

        (writer, dest_id) = self.parameterAsSink(parameters, self.outGrid, context,
                                                                fs, QgsWkbTypes.Polygon, Grid.sourceCrs())
    
        total = Grid.featureCount()
        total = 100.0 / total
        data = {}
        for enum,feature in enumerate(Grid2.getFeatures(QgsFeatureRequest())):
            if total != -1:
                feedback.setProgress(int(enum*total))
            rows = []
            for name in names:
                try:
                    rows.append(feature[name])
                except Exception:
                    feedback.reportError(QCoreApplication.translate('Error', 'Could not find field %s in grid 2 - setting value to -1' % (name)))
                    rows.append(-1)
                    continue
            data[feature['Sample_No_']] = rows

        feedback.pushInfo(QCoreApplication.translate('Contour Grid', 'Creating Contour Grids'))

        fet = QgsFeature(fs)
        for enum, feature in enumerate(Grid.getFeatures(QgsFeatureRequest())):
            if total != -1:
                feedback.setProgress(int(enum * total))
                
            rows = [feature['Sample_No_']]
            fet.setGeometry(feature.geometry())
            rows2 = data[feature['Sample_No_']]
            for enum,name in enumerate(names):
                val = rows2[enum]
                if val == -1:
                    rows.append(val)
                    continue
                else:
                    if stat == 0:
                        v = feature[name] + val
                    elif stat == 1:
                        v = feature[name] - val
                    elif stat == 2:
                        v = feature[name] * val
                    elif stat == 3:
                        v = feature[name] / val
                    if absolute:
                        v = abs(v)
                    rows.append(v)

            fet.setAttributes(rows)
            writer.addFeature(fet, QgsFeatureSink.FastInsert)

        return {self.outGrid:dest_id}
