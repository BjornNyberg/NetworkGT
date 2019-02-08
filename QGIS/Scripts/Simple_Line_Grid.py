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
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature, QgsPointXY, QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsProcessingParameterNumber,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer)
from qgis.utils import iface

class Simple_Grid(QgsProcessingAlgorithm):

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
        return self.tr("NetworkGT")
    
    def shortHelpString(self):
        return self.tr("Create a line grid sampling method")

    def groupId(self):
        return "Topology"
    
    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT"
    
    def createInstance(self):
        return type(self)()
    
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.IB,
            self.tr("Interpretation Boundary"),
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterNumber(
            self.Width,
            self.tr("Spacing"),
            QgsProcessingParameterNumber.Double,
            100.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.Rotation,
            self.tr("Rotation"),
            QgsProcessingParameterNumber.Double,
            0.0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.Grid,
            self.tr("Line Grid"),
            QgsProcessing.TypeVectorPolygon))
    
    def processAlgorithm(self, parameters, context, feedback):
        
        IB = self.parameterAsSource(parameters, self.IB, context)
        
        infc = parameters[self.IB]
        spacing = parameters[self.Width]
        rotation = parameters[self.Rotation]
        iface.mapCanvas().refresh()
        extent = iface.mapCanvas().extent()
        center = iface.mapCanvas().center()
        
        if rotation < 0 or rotation > 180:        
            feedback.reportError(QCoreApplication.translate('Input Error','Rotation value must be within the range of 0 and 180'))
            return {}
            
        fs = QgsFields()
        fs.append(QgsField('Sample_No_', QVariant.Int))
            
        (writer, dest_id) = self.parameterAsSink(parameters, self.Grid, context,
                                            fs, QgsWkbTypes.LineString, IB.sourceCrs())
                                            

        
        feedback.pushInfo(QCoreApplication.translate('TempFiles','Creating Line Grid %s'%(extent)))
        parameters = {'TYPE':1,'EXTENT':extent,'HSPACING':spacing,'VSPACING':spacing,'HOVERLAY':0,'VOVERLAY': 0, 'CRS': infc, 'OUTPUT':'memory:'}  
        grid = st.run('qgis:creategrid',parameters,context=context,feedback=feedback)
        
        parameters = {'INPUT':grid['OUTPUT'],'ANGLE':rotation,'ANCHOR':center,'OUTPUT':'memory:'}  
        rotate = st.run('native:rotatefeatures',parameters,context=context,feedback=feedback)
        
        parameters = {'INPUT':rotate['OUTPUT'],'OVERLAY':infc,'INPUT_FIELDS':'','OVERLAY_FIELDS':'','OUTPUT':'memory:'}   
        tempint = st.run('native:intersection',parameters,context=context,feedback=feedback)    
        
        parameters = {'INPUT':tempint['OUTPUT'],'OUTPUT':'memory:'}  
        tempsp = st.run("native:multiparttosingleparts",parameters,context=context,feedback=feedback)
        
        fet = QgsFeature() 
        count = 0
        for feature in tempsp['OUTPUT'].getFeatures(QgsFeatureRequest()):
            geom = feature.geometry().asPolyline()
            start,end = geom[0],geom[-1]
            startx,starty=start
            endx,endy=end

            dx = endx - startx
            dy =  endy - starty

            angle = math.degrees(math.atan2(dy,dx))
            Bearing = (90.0 - angle) % 360
            if Bearing >= 180:
                Bearing -= 180

            if round (Bearing,0) == round(rotation,0):
                fet.setGeometry(feature.geometry())
                fet.setAttributes([count])
                writer.addFeature(fet,QgsFeatureSink.FastInsert)    
                count += 1

        return {self.Grid:dest_id}