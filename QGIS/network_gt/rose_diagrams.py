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
    
import  os,sys, time,math
import numpy as np
import plotly
import plotly.plotly as py
import plotly.graph_objs as go
import pandas as pd
import collections

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon

from qgis.core import (edit,QgsField, QgsFeature, QgsPointXY,QgsProcessingParameterField,QgsProcessingParameterBoolean, QgsProcessingParameterNumber,QgsProcessingParameterFolderDestination,
QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource,QgsWkbTypes,QgsFeatureSink,
QgsProcessingParameterNumber,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer,QgsProcessingParameterFeatureSink)


class RoseDiagrams(QgsProcessingAlgorithm):

    FN = 'Fracture Network'
    Bins = 'Bins'
    Weight = 'Field'
    Group = "Group"
    
    def __init__(self):
        super().__init__()
        
    def name(self):
        return "Rose Diagram"

    def tr(self, text):
        return QCoreApplication.translate("Rose Diagram", text)

    def displayName(self):
        return self.tr("Rose Diagram")
 
    def group(self):
        return self.tr("Geometry")
    
    def shortHelpString(self):
        return self.tr("Create Weighted Rose Diagram Plots")

    def groupId(self):
        return "Geometry"
    
    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/blob/master/QGIS/README.pdf"
    
    def createInstance(self):
        return type(self)()

    def icon(self):
        pluginPath = os.path.join(os.path.dirname(__file__),'icons')
        return QIcon( os.path.join( pluginPath, 'RD.jpg') )
    
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.FN,
            self.tr("Fracture Network"),
            [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterNumber(
            self.Bins,
            self.tr("Rose Diagram Bin Size"),
            QgsProcessingParameterNumber.Double,
            10.0))
        self.addParameter(QgsProcessingParameterField(self.Weight,
                                self.tr('Weight Field'), parentLayerParameterName=self.FN, type=QgsProcessingParameterField.Numeric, optional=True))
        self.addParameter(QgsProcessingParameterField(self.Group,
                                self.tr('Group Field'), parentLayerParameterName=self.FN, type=QgsProcessingParameterField.Any, optional=True))

    def processAlgorithm(self, parameters, context, feedback):
            
        FN = self.parameterAsSource(parameters, self.FN, context)
        WF = self.parameterAsString(parameters, self.Weight, context)
        G = self.parameterAsString(parameters, self.Group, context)
        bins = parameters[self.Bins]
        
        feedback.pushInfo(QCoreApplication.translate('RoseDiagram','Reading Data'))
        
        data = {}
        
        for feature in FN.getFeatures():
            if G:
                ID = feature[G]
            else:
                ID = 0
            if WF:
                W = feature[WF]
            else:
                W = 1
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
            if ID in data:
                data[ID].append((Bearing,W))
            else:
                data[ID] = [(Bearing,W)]
              

        feedback.pushInfo(QCoreApplication.translate('RoseDiagram','Plotting Data'))

        values = []


        bins = float(bins)
        final = []
        for k,v in data.items():
            
            counts = dict.fromkeys(np.arange(bins,360+bins,bins),0)

            num_values = []
            
            for num in v: #Get the reciprocal of the angle
                if num[0] == 0.0 or num[0] == 180.0:
                    num1 = 0.001  
                else:
                    num1 = num[0]
                if num1 <= 180:
                    num2 = num1 + 180
                else:
                    num2 = num1 - 180
                k1 = int(math.ceil(num1 / bins)) * bins
                k2 = int(math.ceil(num2 / bins)) * bins
                counts[k1] += num[1] #Length weighted polar plot
                counts[k2] += num[1]

            counts = list(counts.values())

            bars = go.Barpolar(r=counts,theta0=bins,name=k)
            final.append(bars)


        layout = go.Layout(
                title='Weighted Rose Diagram',
                font=dict(
                    size=16
                ),
                legend=dict(
                    font=dict(
                        size=16
                    )
                ),
                radialaxis=dict(
                    ticksuffix='%'
                ),
                orientation=0
            )
        
        fig = go.Figure(data=final, layout=layout)
        plotly.offline.plot(fig)
                        
        return {}
