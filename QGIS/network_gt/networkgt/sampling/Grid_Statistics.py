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
import pandas as pd
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (edit,QgsField, QgsFeature, QgsPointXY, QgsProcessingParameterMultipleLayers, QgsProcessingParameterNumber, QgsProcessingParameterEnum, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsProcessingParameterNumber,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer)
from qgis.PyQt.QtGui import QIcon

class GridStats(QgsProcessingAlgorithm):

    mG='Grids'
    outGrid = 'outGrid'
    Stats = 'stats'
    q = 'Quantile'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Grid Statistics"

    def tr(self, text):
        return QCoreApplication.translate("Grid Statistics", text)

    def displayName(self):
        return self.tr("Grid Statistics")

    def group(self):
        return self.tr("2. Sampling")

    def shortHelpString(self):
        return self.tr("A simple method to calculate basic statistics from a series of contour grids for each Sample No ID. Quantile option will return the value at the given quantile from 0 to 1.")

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
        self.addParameter(QgsProcessingParameterMultipleLayers(
            self.mG,
            self.tr("Contour Grids"),
            QgsProcessing.TypeVectorPolygon))

        self.addParameter(QgsProcessingParameterEnum(self.Stats,
                                                     self.tr('Statistics'), options=[self.tr("mean"),self.tr("min"),self.tr("max"),self.tr("std"),self.tr("range"),self.tr("sum"),self.tr("mode"),self.tr("median"),self.tr("kurtosis"),self.tr("skew")],
                                                     defaultValue=0))

        self.addParameter(QgsProcessingParameterNumber(self.q,
                                              self.tr('Quantile'), QgsProcessingParameterNumber.Double, 0.0,
                                              minValue=0.0,maxValue=1.0))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.outGrid,
            self.tr("Calculated Statistics"),
            QgsProcessing.TypeVectorPolygon))

    def processAlgorithm(self, parameters, context, feedback):

        multipleGrids = [QgsVectorLayer(grid.source()) for grid in self.parameterAsLayerList(parameters, self.mG, context)]

        mGlen = len(multipleGrids)
        if mGlen < 2:
            feedback.reportError(QCoreApplication.translate('Error','Must perform statistics on at least 2 contour grids.'))
            return {}

        stat = self.parameterAsInt(parameters, self.Stats, context)
        q = self.parameterAsDouble(parameters, self.q, context)
        gI = multipleGrids[0]

        if gI.fields().indexFromName('Sample_No_') == -1:
            feedback.reportError(QCoreApplication.translate('Error','Contour grid input is invalid - requires a sample no ID.'))
            return {}

        fs = QgsFields()
        fs.append(QgsField("Sample_No_", QVariant.Int))
        names = {'Sample_No_':[]}
        for field in gI.fields():
            if field.type() == QVariant.Double:
                fs.append(QgsField(field.name(), QVariant.Double))
                names[field.name()] = []

        (writer, dest_id) = self.parameterAsSink(parameters, self.outGrid, context,
                                                                fs, QgsWkbTypes.Polygon, gI.sourceCrs())
        df = pd.DataFrame(names)

        geoms = {}
        for enum,grid in enumerate(multipleGrids):
            total = grid.featureCount()
            feedback.pushInfo(QCoreApplication.translate('Contour Grid', 'Analyzing contour grid %s out of %s' % (enum+1,mGlen)))
            total = 100.0 / total

            for enum,feature in enumerate(grid.getFeatures(QgsFeatureRequest())):
                if total != -1:
                    feedback.setProgress(int(enum*total))
                ID = feature['Sample_No_']
                rows = {}
                for name in names.keys():
                    try:
                        rows[name] = feature[name]
                    except Exception:
                        feedback.reportError(QCoreApplication.translate('Error', 'Could not find field %s - setting value to nan' % (name)))
                        rows[name] = np.nan
                        continue

                df = df.append(rows,ignore_index=True)
                if ID not in geoms:
                    geoms[feature['Sample_No_']] = feature.geometry()

        feedback.pushInfo(QCoreApplication.translate('Contour Grid', 'Creating Contour Grids'))
        fet = QgsFeature(fs)
        for n,g in df.groupby('Sample_No_'):
            rows = [n]
            geom = geoms[n]
            fet.setGeometry(geom)

            for name in list(names.keys())[1:]:
                if q > 0:
                    v = g[name].quantile(q)
                elif stat == 0:
                    v = g[name].mean()
                elif stat == 1:
                    v = g[name].min()
                elif stat == 2:
                    v = g[name].max()
                elif stat == 3:
                    v = g[name].std()
                elif stat == 4:
                    v = g[name].max()-g[name].min()
                elif stat == 5:
                    v = g[name].sum()
                elif stat == 6:
                    v = g[name].mode()
                elif stat == 7:
                    v = g[name].median()
                elif stat == 8:
                    v = g[name].kurtosis()
                elif stat == 9:
                    v = g[name].skew()

                rows.append(float(v))

            fet.setAttributes(rows)
            writer.addFeature(fet, QgsFeatureSink.FastInsert)

        return {self.outGrid:dest_id}
