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
import numpy as np
import processing as st
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature, QgsPointXY, QgsProcessingParameterString, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsProcessingParameterNumber,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer)
from qgis.PyQt.QtGui import QIcon

class Sets(QgsProcessingAlgorithm):

    Network = 'Network'
    Sets='Sets'
    Bin_V ='Bins'
    OUTPUT = 'Set Data'
    
    def __init__(self):
        super().__init__()
        
    def name(self):
        return "Define Sets"

    def tr(self, text):
        return QCoreApplication.translate("Sets", text)

    def displayName(self):
        return self.tr("Define Sets")
 
    def group(self):
        return self.tr("Geometry")
    
    def shortHelpString(self):
        return self.tr("Define sets of a fracture network")

    def groupId(self):
        return "Geometry"
    
    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/blob/master/QGIS/README.pdf"
    
    def createInstance(self):
        return type(self)()

    def icon(self):
        pluginPath = os.path.join(os.path.dirname(__file__),'icons')
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
            0.0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr("Set Output"),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback):
            
        Network = self.parameterAsSource(parameters, self.Network, context)
        bin_v =  parameters[self.Bin_V]
        if bin_v > 0:
            x = np.arange(0,180,bin_v)
            y = np.arange(bin_v,180+bin_v,bin_v)
            y[-1] = 180
            bins = tuple(zip(x,y))
        else:
            bins = list(eval(self.parameterAsString(parameters, self.Sets, context)))

        fs = QgsFields()
        f_name = ['Set','Orient','Bin_Mean','Length']    
        for f in f_name:        
            fs.append(QgsField(f, QVariant.Double))

        (writer, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               fs, QgsWkbTypes.LineString, Network.sourceCrs())
                                               
        fet = QgsFeature()                                       
        for feature in Network.getFeatures():
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

            Value = -1
            for enum, b in enumerate(bins):
                if float(b[0]) > float(b[1]):
                    if Bearing >= float(b[0]) or Bearing <= float(b[1]):
                        Value = enum
                        mean = (float(b[0]) - float(180)) + b[1]
                        if mean < 0:
                            mean += 180
                        break
                elif Bearing >= float(b[0]) and Bearing <= float(b[1]):
                    Value = enum 
                    mean = (float(b[0]) + float(b[1]))/2.0
                    break
            
            rows = [Value,Bearing,mean,feature.geometry().length()]

            fet.setGeometry(feature.geometry())
            fet.setAttributes(rows)
            writer.addFeature(fet,QgsFeatureSink.FastInsert)      
            
        
        return {}
