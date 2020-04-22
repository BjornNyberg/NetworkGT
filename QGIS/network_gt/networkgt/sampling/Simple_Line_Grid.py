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

import os, math
import processing as st
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature, QgsPointXY, QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsProcessingParameterNumber,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer)
from qgis.PyQt.QtGui import QIcon

class LineGrid(QgsProcessingAlgorithm):

    IB = 'Interpretation Boundary'
    Width='Spacing'
    Rotation = 'Rotation'
    Grid='Line Grid'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Line Grid"

    def tr(self, text):
        return QCoreApplication.translate("Line_Grid", text)

    def displayName(self):
        return self.tr("Line Grid")

    def group(self):
        return self.tr("2. Sampling")

    def shortHelpString(self):
        return self.tr("Creates a series of equally spaced paralell lines for sampling a fracture network. The user can specify the spacing of the sample lines and their orientations. \n The user can input a fracture linestring or interpretation boundary polygon to define the spatial extent of the sample lines which are then output as a linestring feature. \n N.B. it is recommended that the line samples are orientated approximately perpendicular to the fracture population of interest.\n Please refer to the help button for more information.")

    def groupId(self):
        return "2. Sampling"

    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/wiki/2.-Sampling-Methods"

    def createInstance(self):
        return type(self)()

    def icon(self):
        n,path = 2,os.path.dirname(__file__)
        while(n):
            path=os.path.dirname(path)
            n -=1
        pluginPath = os.path.join(path,'icons')
        return QIcon( os.path.join( pluginPath, 'LG.jpg') )

    def initAlgorithm(self, config):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.IB,
            self.tr("Fracture Network or Interpretation Boundary"),
            [QgsProcessing.TypeVectorPolygon,QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterNumber(
            self.Width,
            self.tr("Spacing"),
            QgsProcessingParameterNumber.Double,
            100.0,minValue=0.000001))
        self.addParameter(QgsProcessingParameterNumber(
            self.Rotation,
            self.tr("Rotation"),
            QgsProcessingParameterNumber.Double,
            0.0,minValue=0.0,maxValue=180.0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.Grid,
            self.tr("Line Grid"),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback):

        IB = self.parameterAsVectorLayer(parameters, self.IB, context)

        infc = parameters[self.IB]
        spacing = parameters[self.Width]
        rotation = parameters[self.Rotation]

        fs = QgsFields()
        fs.append(QgsField('Sample_No_', QVariant.Int))

        (writer, dest_id) = self.parameterAsSink(parameters, self.Grid, context,
                                            fs, QgsWkbTypes.LineString, IB.sourceCrs())

        features = IB.selectedFeatures()
        if len(features) == 0:
            features = IB.getFeatures()
            extent = IB.extent()
        else:
            extent = IB.boundingBoxOfSelected()

        feedback.pushInfo(QCoreApplication.translate('TempFiles','Creating Line Grid'))
        parameters = {'TYPE':1,'EXTENT':extent,'HSPACING':spacing,'VSPACING':spacing,'HOVERLAY':0,'VOVERLAY': 0, 'CRS': infc, 'OUTPUT':'memory:'}
        grid = st.run('qgis:creategrid',parameters,context=context,feedback=feedback)

        if rotation > 0:
            center = extent.center()
            parameters = {'INPUT':grid['OUTPUT'],'ANGLE':rotation,'ANCHOR':center,'OUTPUT':'memory:'}
            rotate = st.run('native:rotatefeatures',parameters,context=context,feedback=feedback)
            outFeats = rotate['OUTPUT']
        else:
            outFeats = grid['OUTPUT']

        if IB.wkbType() == 3 or IB.wkbType() == 6:
            cursorm = [feature.geometry() for feature in features]
        else:
            cursorm = [QgsGeometry.fromRect(extent)]

        fet = QgsFeature()
        count = 0
        for feature in outFeats.getFeatures():
            curGeom = feature.geometry()

            for m in cursorm:
                if curGeom.intersects(m):

                    intGeom = curGeom.intersection(m)
                    try:
                        if intGeom.isMultipart():
                            geom = intGeom.asMultiPolyline()
                        else:
                            geom = [intGeom.asPolyline()]
                    except Exception:
                        continue

                    for part in geom:
                        start,end = part[0],part[-1]
                        startx,starty=start
                        endx,endy=end

                        dx = endx - startx
                        dy =  endy - starty

                        angle = math.degrees(math.atan2(dy,dx))
                        Bearing = (90.0 - angle) % 360
                        if Bearing >= 180:
                            Bearing -= 180

                        if round (Bearing,0) == round(rotation,0):
                            points = [QgsPointXY(startx,starty),QgsPointXY(endx,endy)]
                            outGeom = QgsGeometry.fromPolylineXY(points)
                            fet.setGeometry(outGeom)
                            fet.setAttributes([count])
                            writer.addFeature(fet,QgsFeatureSink.FastInsert)
                            count += 1

        return {self.Grid:dest_id}
