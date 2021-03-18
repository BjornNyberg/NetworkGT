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

import os, math, tempfile, string, random
from qgis.PyQt.QtCore import QCoreApplication, QVariant

from qgis.core import *
from qgis.PyQt.QtGui import QIcon

class permTensorPlot(QgsProcessingAlgorithm):

    TP = 'Topology Parameters'
    norm = 'Norm'
    combine = 'Combine'
    export = 'Export'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Plot Permeability Ellipse"

    def tr(self, text):
        return QCoreApplication.translate("Plot Permeability Ellipse", text)

    def displayName(self):
        return self.tr("Plot Permeability Ellipse")

    def group(self):
        return self.tr("5. Flow")

    def shortHelpString(self):
        return self.tr("Plots the effective permeability tensor for a given sample area as an ellipse. The principle axes of the ellipse are defined as the square root of the maximum permeability (K1) and minimum peremability (K2), which are given in millidarcy's (mD). \n The input requires a topology parameters polygon/contour grid with permeability parameters K1, K2 and the K1 azimuth, which can be calculated using the Permeability Tensor tool.\n Please refer to the help button for more information.")

    def groupId(self):
        return "5. Flow"

    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/wiki/5.-Flow-Assessment"

    def createInstance(self):
        return type(self)()

    def initAlgorithm(self, config=None):

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.TP,
            self.tr("Permeability Parameters"),
            [QgsProcessing.TypeVectorPolygon]))

        self.addParameter(QgsProcessingParameterBoolean(self.norm,
                    self.tr("Normalise Equal Area"),False))
        self.addParameter(QgsProcessingParameterBoolean(self.combine,
                    self.tr("Combine"),True))

    def processAlgorithm(self, parameters, context, feedback):

        TP = self.parameterAsLayer(parameters, self.TP, context)
        combine = parameters[self.combine]
        norm = parameters[self.norm]

        try:
            import plotly.graph_objs as go
            import numpy as np
            import chart_studio.plotly as py
        except Exception:
            feedback.reportError(QCoreApplication.translate('Error','Error please install the necessary dependencies.'))
            return {}

        if TP.fields().indexFromName('Kxx') == -1:
            feedback.reportError(QCoreApplication.translate('Error','Permeability Tensor input is invalid - please run the permeability tensor tool prior to plotting'))
            return {}

        traces,maxV = [],[]

        features = TP.selectedFeatures()
        total = TP.selectedFeatureCount()
        if len(features) == 0:
            features = TP.getFeatures()
            total = TP.featureCount()
        total = 100.0/total

        for enum,feature in enumerate(features):
            if total != -1:
                feedback.setProgress(int(enum*total))
            try:
                FID = feature['Sample_No_']
                K1 = feature['K1']
                K2 = feature['K2']
                K1a = feature['K1 Azimuth']
                trace = []
                eX,eY = [],[]

                K1 = math.sqrt(K1)
                K2 = math.sqrt(K2)

                if norm:
                    K2 = K2/K1
                    K1 = 1.0
                else:
                    K1 /= 2
                    K2 /= 2

                for n in np.arange(0,360.5,0.5):
                    x = ((K1)*(math.cos(math.radians(n)))*(math.cos(math.radians(90-K1a))))-((K2)*(math.sin(math.radians(n)))*(math.sin(math.radians(90-K1a))))
                    y = ((K1)*(math.cos(math.radians(n)))*(math.sin(math.radians(90-K1a))))+((K2)*(math.sin(math.radians(n)))*(math.cos(math.radians(90-K1a))))
                    eX.append(x)
                    eY.append(y)

                maxV.append(K1)

                k1Y,k1X = [math.cos(K1a*(math.pi/180))*K1,(math.cos(K1a*(math.pi/180))*K1)*-1],[math.sin(K1a*(math.pi/180))*K1,(math.sin(K1a*(math.pi/180))*K1)*-1]
                k2Y,k2X = [math.cos((K1a+90)*(math.pi/180))*K2,(math.cos((K1a+90)*(math.pi/180))*K2)*-1],[math.sin((K1a+90)*(math.pi/180))*K2,(math.sin((K1a+90)*(math.pi/180))*K2)*-1]

                trace.append(go.Scatter(x = eX, y = eY,mode = 'lines', name = 'Sample No - %s'%(FID), legendgroup = str(FID), line = dict(color='blue', width=1.5,)))
                trace.append(go.Scatter(x = k1X, y = k1Y,mode = 'lines', name ='K1', legendgroup = str(FID), line = dict(color='red', width=1.5),showlegend = False))
                trace.append(go.Scatter(x = k2X, y = k2Y,mode = 'lines', name ='K2', legendgroup = str(FID), line = dict(color='red', width=1.5),showlegend = False))

                if combine:
                    traces.extend(trace)
                else:
                    traces.append(trace)

            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Error',str(e)))
                break

        nTraces = int(len(traces)/3)
        feedback.pushInfo(QCoreApplication.translate('Info','Plotting %s permeability ellipse(s).' %(nTraces)))
            
        if combine:
            traces = [traces]

        for enum,trace in enumerate(traces):
            if norm:
                r = 1
            elif combine:
                r = max(maxV)
            else:
                r = maxV[enum]*1.05

            ngtPath = 'https://raw.githubusercontent.com/BjornNyberg/NetworkGT/master/Images/NetworkGT_Logo1.png'
            layout = dict(images=[dict(source=ngtPath,xref="paper", yref="paper", x=1.3, y=1.0,sizex=0.4, sizey=0.4, xanchor="right", yanchor="bottom")],
                  xaxis = dict(range=[-r, r]),
                  yaxis = dict(range=[-r, r]),
                  width=650, height=650,)

            fig = go.Figure(trace, layout=layout)
            try:
                py.plot(fig, filename='Tensor Plot', auto_open=True)
            except Exception:
                fig.show()

        return {}
