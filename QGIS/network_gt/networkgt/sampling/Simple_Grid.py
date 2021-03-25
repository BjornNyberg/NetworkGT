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
from qgis.core import (edit,QgsProcessingParameterBoolean,QgsField, QgsFeature, QgsPointXY, QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsProcessingParameterNumber,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer)
from qgis.PyQt.QtGui import QIcon

class ContourGrid(QgsProcessingAlgorithm):

    IB = 'Interpretation Boundary'
    Width='Spacing'
    Radius = 'Radius'
    Grid='Grid'
    Rotation = 'Rotation'
    Within = 'Within'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Contour Grid"

    def tr(self, text):
        return QCoreApplication.translate("Simple_Grid", text)

    def displayName(self):
        return self.tr("Contour Grid")

    def group(self):
        return self.tr("2. Sampling")

    def shortHelpString(self):
        return self.tr("Creates a contour grid of polygons for sampling a fracture network. The user can specify the grid cell dimensions. Each grid cell samples the network using a circle sample with a user defined radius. \n The user can input a fracture linestring or interpretation boundary polygon to define the spatial extent of the contour grid which is then output as a polgyon feature. \n N.B. It is important to choose an appropriate radius for the circle samples in order to sample a representative area of the fracture network.\n Please refer to the help button for more information.")

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
        return QIcon( os.path.join( pluginPath, 'CG.jpg') )

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
            self.Radius,
            self.tr("Radius"),
            QgsProcessingParameterNumber.Double,
            250.0,minValue=0.01))
        self.addParameter(QgsProcessingParameterNumber(
            self.Rotation,
            self.tr("Rotation"),
            QgsProcessingParameterNumber.Double,
            0.0,minValue=0.0,maxValue=90.0))
        self.addParameter(QgsProcessingParameterBoolean(self.Within, self.tr("Grid Within Interpretation Boundary"), False))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.Grid,
            self.tr("Grid"),
            QgsProcessing.TypeVectorPolygon))

    def processAlgorithm(self, parameters, context, feedback):

        IB = self.parameterAsVectorLayer(parameters, self.IB, context)

        features = IB.selectedFeatures()

        if len(features) == 0:
            features = IB.getFeatures()
            extent = IB.extent()
        else:
            extent = IB.boundingBoxOfSelected()

        if IB.wkbType() == 3 or IB.wkbType() == 6:
            field_check = IB.fields().indexFromName('2D Intensity')
            if field_check != -1:
                for enum,feature in enumerate(IB.getFeatures()):
                    intensity = round(feature['2D Intensity'], 4)
                if enum > 1:
                    feedback.reportError(QCoreApplication.translate('Error','Warning - Require one topology parameters dataset for the entire region to calculate suggested radius and spacing.'))
                    return {}
                radius = round((1 / intensity) * 4, 4)
                spacing = round(radius / 4.0, 4)
                feedback.reportError(QCoreApplication.translate('Interpretation Boundary','Info - Applying a calculated sampling radius of %s and a spacing of %s based on a 2D intensity of %s. It is recommended to review and adjust parameters based on branch and node results.' % (radius, spacing, intensity)))
                cursorm = [feature.geometry() for feature in features]
            else:
                feedback.reportError(QCoreApplication.translate('Error', 'Warning - Require a topology parameters or fracture trace lengths input to calculate suggested sampling radius and spacing.'))
                return {}
        else:
            spacing = parameters[self.Width]
            radius = parameters[self.Radius]
            cursorm = [QgsGeometry.fromRect(extent)]

        rotation = parameters[self.Rotation]
        w = parameters[self.Within]

        if radius < spacing:
            feedback.reportError(QCoreApplication.translate('Error', 'Warning - Contour grid spacing is less than the specified sampling radius.'))
            return {}

        if rotation == 0.0:
            r = 0.00001
        else:
            r = rotation

        fs = QgsFields()
        field_names = [QgsField('Sample_No_', QVariant.Int),
                            QgsField('Area', QVariant.Double),
                            QgsField('Circ', QVariant.Double),
                            QgsField('Radius', QVariant.Double),
                            QgsField('Rotation', QVariant.Double),
                            QgsField('Spacing', QVariant.Double)]

        for f in field_names:
            fs.append(f)

        (writer, dest_id) = self.parameterAsSink(parameters, self.Grid, context,
                                                                fs, QgsWkbTypes.Polygon, IB.sourceCrs())

        feedback.pushInfo(QCoreApplication.translate('TempFiles','Creating Grid'))

        parameters = {'TYPE':2,'EXTENT':extent,'HSPACING':spacing,'VSPACING':spacing,'HOVERLAY':0,'VOVERLAY': 0, 'CRS': IB, 'OUTPUT':'memory:'}
        grid = st.run('qgis:creategrid',parameters,context=context,feedback=feedback)

        center = extent.center()
        try:
            parameters = {'INPUT':grid['OUTPUT'],'ANGLE':r,'ANCHOR':center,'OUTPUT':'memory:'}
            rotate = st.run('native:rotatefeatures',parameters,context=context,feedback=feedback)
        except Exception: ##TO DO Fix current bug associated with extent and anchor calculation
            parameters = {'INPUT':grid['OUTPUT'],'ANGLE':r,'ANCHOR':center,'OUTPUT':'memory:'}
            rotate = st.run('native:rotatefeatures',parameters,context=context,feedback=feedback)

        outFeats = rotate['OUTPUT']
        total = outFeats.featureCount()
        total = 100.0/total

        fet = QgsFeature()
        for enum,feature in enumerate(outFeats.getFeatures()):
            if total != -1:
                feedback.setProgress(int(enum*total))
            geom = feature.geometry()

            for m in cursorm:
                if w:
                    if not geom.within(m):
                        continue
                buff = geom.centroid().buffer(float(radius),100)
                geom2 = buff.intersection(m)
                length = geom2.length()
                area = geom2.area()
                rows = [feature.id(),area,length,float(radius),rotation,spacing]
                fet.setGeometry(geom)
                fet.setAttributes(rows)
                writer.addFeature(fet,QgsFeatureSink.FastInsert)
                break

        return {self.Grid:dest_id}