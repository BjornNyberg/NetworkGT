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
import numpy as np
import pandas as pd
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (edit,QgsField, QgsProcessingParameterField,QgsFeature, QgsProcessingParameterBoolean, QgsProcessingParameterMultipleLayers, QgsProcessingParameterNumber, QgsProcessingParameterEnum, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsProcessingParameterNumber,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer)
from qgis.PyQt.QtGui import QIcon
from PyQt5.QtCore import QDate, QDateTime
import PyQt5

class GridPlot(QgsProcessingAlgorithm):

    Grid='Grid'
    X = 'X'
    Y = 'Y'
    Z = 'Z'
    Grp = 'Group'
    Size = 'Size'
    Time = 'Time'
    Speed = 'Speed'
    A = 'Animate'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Grid Plots"

    def tr(self, text):
        return QCoreApplication.translate("Grid Plots", text)

    def displayName(self):
        return self.tr("Grid Plots")

    def group(self):
        return self.tr("2. Sampling")

    def shortHelpString(self):
        return self.tr('''Create a series of grid plots and time animated grid plots using Plotly. User can provide a X field to create a histogram plot, X and Y field to create a scatter plot or a X, Y and Z field to create a ternary diagram.
        The Time Field will sort the data by the provided field and must be supplied if the animate check box is selected. In addition, the user may optionally specify a sortby, groupby and size fields in the creation of plots.''')

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
        self.addParameter(QgsProcessingParameterFeatureSource(self.Grid, self.tr("Contour Grid")))
        self.addParameter(QgsProcessingParameterField(self.X, self.tr('X value'), 'Step', parentLayerParameterName=self.Grid, type=QgsProcessingParameterField.Numeric))
        self.addParameter(QgsProcessingParameterField(self.Y, self.tr('Y value'), 'Tracer', parentLayerParameterName=self.Grid, type=QgsProcessingParameterField.Numeric,optional=True))
        self.addParameter(QgsProcessingParameterField(self.Z, self.tr('Z value'), parentLayerParameterName=self.Grid, type=QgsProcessingParameterField.Numeric,optional=True))
        self.addParameter(QgsProcessingParameterField(self.Size, self.tr('Size'), parentLayerParameterName=self.Grid, type=QgsProcessingParameterField.Numeric, optional=True))
        self.addParameter(QgsProcessingParameterField(self.Grp, self.tr('Groupby Field'),'Sample_No_', parentLayerParameterName=self.Grid,optional=True))
        self.addParameter(QgsProcessingParameterField(self.Time, self.tr('Time or Sortby Field'), parentLayerParameterName=self.Grid,optional=True))
        self.addParameter(QgsProcessingParameterBoolean(self.A, self.tr("Animate"), False))

        self.addParameter(QgsProcessingParameterNumber(
            self.Speed,
            self.tr("Animation Speed"),
            QgsProcessingParameterNumber.Double,
            1000,minValue=10))


    def processAlgorithm(self, parameters, context, feedback):

        Grid = self.parameterAsVectorLayer(parameters, self.Grid, context)

        try:
            import pandas as pd
            import plotly.graph_objs as go
            import plotly.express as px
            import chart_studio.plotly as py
        except Exception:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            feedback.reportError(QCoreApplication.translate('Error',' '))
            feedback.reportError(QCoreApplication.translate('Error','Error loading modules - please install the necessary dependencies'))
            return {}

        X = self.parameterAsString(parameters, self.X, context)
        Y = self.parameterAsString(parameters, self.Y, context)
        Z = self.parameterAsString(parameters, self.Z, context)
        S = self.parameterAsString(parameters, self.Size, context)
        T = self.parameterAsString(parameters, self.Time, context)
        G = self.parameterAsString(parameters, self.Grp, context)
        speed = parameters[self.Speed]
        A = parameters[self.A]

        if A and T == '':
            feedback.reportError(QCoreApplication.translate('Error','Error - Please select a Time Field for animations.'))
            return {}

        names = [X,Y,Z,S,T,G]
        vNames = {}
        for n in names:
            if n != '':
                vNames[n] = []

        features = Grid.selectedFeatures()

        if len(features) == 0:
            features = Grid.getFeatures()
            total = Grid.featureCount()
        else:
            total = len(features)

        total = 100.0/total

        for enum,feature in enumerate(features):
            if total != -1:
                feedback.setProgress(int(enum*total))
            for name in vNames.keys():
                try:
                    v = feature[name]
                    if type(v) == PyQt5.QtCore.QDateTime:
                        v = v.toPyDateTime().strftime('%d/%m/%Y, %H:%M:%S')
                    vNames[name].append(v)
                except Exception:
                    vNames[name].append(0)
                    continue

        df = pd.DataFrame(vNames)
        if S == '':
            df['Size'] = 10
            S = 'Size'

        if G == '':
            df['Trace'] = '1'
            G = 'Trace'

        df[G] = df[G].astype(str)

        if A:
            df.sort_values(by=[T], inplace=True)
            if Y:
                if Z:
                    fig = px.scatter_ternary(df, a=X, b=Y, c=Z, animation_frame=T, color=G,size=S)
                else:
                    xRange = [df[X].min()*0.9,df[X].max()*1.1]
                    yRange = [df[Y].min()*0.9,df[Y].max()*1.1]
                    fig = px.scatter(df, x=X, y=Y, animation_frame=T, color=G,size=S,range_x=xRange,range_y=yRange)

            else:
                if G == '':
                    fig = px.histogram(df, x=X, animation_frame=T)
                else:
                    fig = px.histogram(df, x=X, animation_frame=T, color=G)

            fig.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = speed

        else:
            if T != '':
                df.sort_values(by=[T], inplace=True)
            if Y:
                if Z:
                    fig = px.scatter_ternary(df, a=X, b=Y, c=Z, color=G,size=S)
                else:
                    xRange = [df[X].min()*0.9,df[X].max()*1.1]
                    yRange = [df[Y].min()*0.9,df[Y].max()*1.1]
                    if T == '':
                        fig = px.scatter(df, x=X, y=Y, color=G,size=S,range_x=xRange,range_y=yRange)
                    else:
                        fig = px.line(df, x=X, y=Y, color=G,range_x=xRange,range_y=yRange)
            else:
                if G == '':
                    fig = px.histogram(df, x=X)
                else:
                    fig = px.histogram(df, x=X, color=G)

        try:
            py.plot(fig, filename='Animation', auto_open=True)
        except Exception as e:
            fig.show()

        return {}
