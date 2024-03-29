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

import  os,math

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.core import *

class RoseDiagrams(QgsProcessingAlgorithm):

    FN = 'Fracture Network'
    Bins = 'Bins'
    Weight = 'Field'
    Group = 'Group'
    SR ='Equal Area'
    P ='Percentage'
    R = 'Reverse'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Rose Diagram"

    def tr(self, text):
        return QCoreApplication.translate("Rose Diagram", text)

    def displayName(self):
        return self.tr("Rose Diagram")

    def group(self):
        return self.tr("3. Geometry")

    def shortHelpString(self):
        return self.tr("Creates weighted rose diagram of fracture orientations. The user has the option of selecting an attribute field to weight orientaitons (e.g. by length). It is recommended to tick the equal-area plot option in order to avoid visual bias of orientation trends. \n The input data needs to be a fracture network linestring and the rose diagrams are output in an external browser window. \n Please refer to the help button for more information.")

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
            10.0,minValue=1.0))
        self.addParameter(QgsProcessingParameterField(self.Weight,
                                self.tr('Weight Field'), parentLayerParameterName=self.FN, type=QgsProcessingParameterField.Numeric, optional=True))
        self.addParameter(QgsProcessingParameterField(self.Group,
                                self.tr('Group Field'), parentLayerParameterName=self.FN, type=QgsProcessingParameterField.Any, optional=True))
        self.addParameter(QgsProcessingParameterBoolean(self.SR,
                    self.tr("Equal Area"),False))
        self.addParameter(QgsProcessingParameterBoolean(self.P,
                    self.tr("Percentage"),False))
        self.addParameter(QgsProcessingParameterBoolean(self.R,
                                                        self.tr("Plot Reciprocal Angle"), False))

    def processAlgorithm(self, parameters, context, feedback):

        try:
            import pandas as pd
            import numpy as np
            import plotly.graph_objs as go
            import chart_studio.plotly as py
        except Exception:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            feedback.reportError(QCoreApplication.translate('Error',' '))
            feedback.reportError(QCoreApplication.translate('Error','Error loading modules - please install the necessary dependencies'))
            return {}

        FN = self.parameterAsLayer(parameters, self.FN, context)
        WF = self.parameterAsString(parameters, self.Weight, context)
        G = self.parameterAsString(parameters, self.Group, context)
        bins = parameters[self.Bins]
        SR = parameters[self.SR]
        P = parameters[self.P]
        R = parameters[self.R]

        feedback.pushInfo(QCoreApplication.translate('RoseDiagram','Reading Data'))

        data = {}

        features = FN.selectedFeatures()
        total = FN.selectedFeatureCount()
        if len(features) == 0:
            features = FN.getFeatures()
            total = FN.featureCount()

        total = 100.0/total
        for enum,feature in enumerate(features):
            if total > 0:
                feedback.setProgress(int(enum*total))
            if G:
                ID = feature[G]
            else:
                ID = 0
            if WF:
                W = feature[WF]
                if type(W) == int or type(W) == float:
                    pass
                else:
                    feedback.reportError(QCoreApplication.translate('Error','Weight field contains non numeric values - check for null values'))
                    return {}
            else:
                W = 1

            geom = feature.geometry()
            v = geom.length()
            if QgsWkbTypes.isSingleType(geom.wkbType()):
                geom = [geom.asPolyline()]
            else:
                geom = geom.asMultiPolyline()

            if len(geom) == 0:
                feedback.reportError(QCoreApplication.translate('Error','Warning - skipping null geometry linestring.'))
                continue

            x,y = 0,0
            for part in geom:
                startx = None
                for point in part:
                    if startx == None:
                        startx,starty = point
                        continue
                    endx,endy=point

                    dx = endx - startx
                    dy =  endy - starty

                    l = math.sqrt((dx**2)+(dy**2))
                    angle = math.degrees(math.atan2(dy,dx))
                    x += math.cos(math.radians(angle)) * l
                    y += math.sin(math.radians(angle)) * l

                    startx,starty = endx,endy

            mean = 90 - np.around(math.degrees(math.atan2(y, x)), decimals=4)
            if mean > 180:
                mean -= 180
            elif mean < 0:
                mean += 180

           # mean = np.around(math.degrees(math.atan2(y, x)), decimals=4) #Simplified angle calculation
           # mean = mean%360
           # if mean > 180:
           #     mean -= 180

            if ID in data:
                data[ID].append((mean,W))
            else:
                data[ID] = [(mean,W)]

        feedback.pushInfo(QCoreApplication.translate('RoseDiagram','Plotting Data'))

        values = []

        bins = float(bins)
        final = []
        values = []

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
                counts[k1] += num[1]  # Length weighted polar plot
                if R:
                    k2 = int(math.ceil(num2 / bins)) * bins
                    counts[k2] += num[1]

            count = list(counts.values())
            if SR:
                count = [math.sqrt(c) for c in count]

            if P:
                total = float(sum(count))
                count = [(c/total)*100 for c in count]

            binsV = [k - (bins/2.0) for k in counts.keys()]

            bars = go.Barpolar(r=count,theta=binsV,name=k)

            final.append(bars)

        ngtPath = 'https://raw.githubusercontent.com/BjornNyberg/NetworkGT/master/Images/NetworkGT_Logo1.png'
        if R:
            layout = go.Layout(
                images=[dict(source=ngtPath, xref="paper", yref="paper", x=0.85, y=0.05, sizex=0.2, sizey=0.2,
                             xanchor="right", yanchor="bottom")],
                title='Weighted Rose Diagram', font=dict(size=16), legend=dict(font=dict(size=16)),
                polar=dict(angularaxis=dict(direction="clockwise", tickfont=dict(size=14)), ), )
        else:
            layout = go.Layout(
                    images=[dict(source=ngtPath,xref="paper", yref="paper", x=0.85, y=0.05,sizex=0.2, sizey=0.2, xanchor="right", yanchor="bottom")],
                    title='Weighted Rose Diagram',font=dict(size=16),legend=dict(font=dict(size=16)),
                    polar=dict(angularaxis=dict(direction="clockwise",tickfont=dict(size=14)),sector = [-90,90]),)
            
        fig = go.Figure(final, layout=layout)
        try:
            py.plot(fig, filename='Rose Diagram', auto_open=True)
        except Exception as e:
            fig.show()

        return {}
