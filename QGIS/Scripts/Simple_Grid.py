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
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (edit,QgsField, QgsFeature, QgsPointXY, QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsProcessingParameterNumber,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer)
from qgis.utils import iface

class Simple_Grid(QgsProcessingAlgorithm):

    IB = 'Interpretation Boundary'
    Width='Spacing'
    Radius = 'Radius'
    Grid='Grid'
    
    def __init__(self):
        super().__init__()
        
    def name(self):
        return "Contour Grid"

    def tr(self, text):
        return QCoreApplication.translate("Simple_Grid", text)

    def displayName(self):
        return self.tr("Contour Grid")
 
    def group(self):
        return self.tr("NetworkGT")
    
    def shortHelpString(self):
        return self.tr("Create a contour grid sampling method")

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
            self.Radius,
            self.tr("Radius"),
            QgsProcessingParameterNumber.Double,
            250.0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.Grid,
            self.tr("Grid"),
            QgsProcessing.TypeVectorPolygon))
    
    def processAlgorithm(self, parameters, context, feedback):
        
        def no_post_process(alg, context, feedback):
            pass
            
        IB = self.parameterAsSource(parameters, self.IB, context)
        
        fs = QgsFields()
        field_names = [QgsField('Sample_No_', QVariant.Int),
                            QgsField('Area', QVariant.Double),
                            QgsField('Circumfere', QVariant.Double),
                            QgsField('Radius', QVariant.Double)]
                            
        for f in field_names:
            fs.append(f)
            
        (writer, dest_id) = self.parameterAsSink(parameters, self.Grid, context,
                                            fs, QgsWkbTypes.Polygon, IB.sourceCrs())
                                            
        infc = parameters[self.IB]
        spacing = parameters[self.Width]
        radius = parameters[self.Radius]
        
        feedback.pushInfo(QCoreApplication.translate('TempFiles','Creating Grid'))
        parameters = {'TYPE':2,'EXTENT':infc,'HSPACING':spacing,'VSPACING':spacing,'HOVERLAY':0,'VOVERLAY': 0, 'CRS': infc, 'OUTPUT':'memory:'}  
        grid = st.run('qgis:creategrid',parameters,context=context,feedback=feedback)#, onFinish=no_post_process)   

        cursorm = [feature.geometry() for feature in IB.getFeatures(QgsFeatureRequest())]
        fet = QgsFeature() 
        for feature in grid['OUTPUT'].getFeatures(QgsFeatureRequest()):
            geom = feature.geometry()
            for m in cursorm:
                if geom.within(m):
                    buffer = geom.buffer(float(radius),5)
                    geom2 = buffer.intersection(m)          
                    length = geom2.length()
                    area = geom2.area()
                    rows = [feature.id(),area,length,float(radius)]
                    
                    fet.setGeometry(geom)
                    fet.setAttributes(rows)
                    writer.addFeature(fet,QgsFeatureSink.FastInsert)    
                    
                    break

        return {self.Grid:dest_id}