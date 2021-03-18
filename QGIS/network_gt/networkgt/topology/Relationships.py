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

import os, warnings
import processing as st
from math import ceil
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import *
from qgis.PyQt.QtGui import QIcon
from itertools import cycle

class Relationships(QgsProcessingAlgorithm):

    Fractures = 'Fractures'
    Errors = 'Errors'
    dCount = 'dCount'
    dCountm = 'dCountm'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Plot Topological Relationships"

    def tr(self, text):
        return QCoreApplication.translate("Plot Topological Relationships", text)

    def displayName(self):
        return self.tr("Relationships")

    def group(self):
        return self.tr("4. Topology")

    def shortHelpString(self):
        return self.tr("Plot cross-cutting and abutting relationships between fracture sets")

    def groupId(self):
        return "4. Topology"

    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/wiki/4.-Topology-Analysis"

    def createInstance(self):
        return type(self)()

  #  def icon(self):
  #      n,path = 2,os.path.dirname(__file__)
  #      while(n):
  #          path=os.path.dirname(path)
  #          n -=1
  #      pluginPath = os.path.join(path,'icons')
  #      return QIcon( os.path.join( pluginPath, 'TP.jpg') )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Fractures,
            self.tr("Fractures"),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterNumber(
            self.dCount,
            self.tr("Min Count"),
            QgsProcessingParameterNumber.Double,
            0.0,minValue=0.0))

        self.addParameter(QgsProcessingParameterNumber(
            self.dCountm,
            self.tr("Max Count"),
            QgsProcessingParameterNumber.Double,
            0.0,minValue=0.0))

        self.addParameter(QgsProcessingParameterBoolean(self.Errors,
                                                    self.tr("Ignore Self Intersections"), False))


    def processAlgorithm(self, parameters, context, feedback):

        try:
            import pandas as pd
            import numpy as np
            import plotly.graph_objs as go
            import plotly.express as px
            import chart_studio.plotly as py
        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            feedback.reportError(QCoreApplication.translate('Error',' '))
            feedback.reportError(QCoreApplication.translate('Error','Error loading modules - please install the necessary dependencies'))
            return {}

        Network = self.parameterAsSource(parameters, self.Fractures, context)
        infc = parameters[self.Fractures]
        er = parameters[self.Errors]
        dCount = parameters[self.dCount]
        dCountm = parameters[self.dCountm]

        if Network.fields().indexFromName('Set') == -1:
            feedback.reportError(QCoreApplication.translate('Error','Fractures input is invalid - please run the sets tool prior to calculting the set relationships.'))
            return {}

        if Network.fields().indexFromName('Class') != -1:
            feedback.reportError(QCoreApplication.translate('Error','Warning - It is recommended to use the fractures trace lengths rather than branches to calculate set relationships.'))

        params = {'INPUT':infc,'LINES':infc,'OUTPUT':'memory:'}
        templines = st.run('native:splitwithlines',params,context=context,feedback=feedback)

        features = templines['OUTPUT'].getFeatures(QgsFeatureRequest())

        c,s = [],[]
        P = 1000000

        feedback.pushInfo(QCoreApplication.translate('TempFiles', 'Defining Node Intersections'))
        #i=0
        total = templines['OUTPUT'].featureCount()
        total = 100.0/total
        for enum,feature in enumerate(features):
            if total != -1:
                feedback.setProgress(int(enum*total))
            geom = feature.geometry()
            if geom.length() < 0.0000001:
                continue
            if QgsWkbTypes.isSingleType(geom.wkbType()):
                geom = [geom.asPolyline()]
            else:
                geom = geom.asMultiPolyline()
            start, end = geom[0][0], geom[-1][-1]
            startx,starty=start
            endx,endy=end
            branch = [(ceil(startx*P)/P,ceil(starty*P)/P),(ceil(endx*P)/P,ceil(endy*P)/P)]
            setV = int(feature['Set'])
            for b in branch:
                c.append(b)
                s.append(setV)

        df = pd.DataFrame({'Coord': c, 'Sets': s})
        del c,s
        if len(df.Sets.unique()) < 2:
            feedback.reportError(QCoreApplication.translate('Error','Require at least two sets to calculate topological relationships.'))
            return {}

        feedback.pushInfo(QCoreApplication.translate('TempFiles', 'Creating and Plotting Data'))

        nError = 0
        dataS,dataN = [],[]
        for n,g in df.groupby('Coord'):
            sets = sorted(g.Sets.unique())

            gLen = len(g)
            if gLen == 4:
                if len(sets) == 1:
                    if er == True:
                        continue
                    name = 'Sets %s and %s cross-cut.' % (sets[0], sets[0])
                    s = 'Sets %s and %s' % (sets[0], sets[0])
                elif len(sets) == 2:
                    name = 'Sets %s and %s cross-cut.'%(sets[0],sets[1])
                    s = 'Sets %s and %s' % (sets[0], sets[1])
                else:
                    nError += 1
                    if nError < 10:
                        feedback.reportError(QCoreApplication.translate('Interpretation Boundary',
                                                                       'Error - found a cross-cutting intersection at node %s with %s set(s).'%(n,len(sets))))
                    elif nError == 10:
                        feedback.reportError(QCoreApplication.translate('Interpretation Boundary',
                                                                        'Reached 10 errors and will stop reporting errors.'))
                    name = 'Errors'
                    s = 'Errors'

            elif gLen == 3:
                try:
                    if len(sets) == 2:
                        setsV = sorted(g.Sets)
                        if setsV[0] == setsV[1]:
                            name = 'Set %s abuts set %s.' % (setsV[2], setsV[0])
                            s = 'Sets %s and %s' % (setsV[2], setsV[0])
                        else:
                            name = 'Set %s abuts set %s.' % (setsV[0], setsV[1])
                            s = 'Sets %s and %s' % (setsV[0], setsV[1])
                    elif len(sets) == 1:
                        if er == True:
                            continue
                        name = 'Set %s abuts set %s.' % (sets[0], sets[0])
                        s = 'Sets %s and %s' % (sets[0], sets[0])
                    else:
                        nError += 1
                        if nError < 10:
                            feedback.reportError(QCoreApplication.translate('Interpretation Boundary', 'Error - found an abutting intersection at node %s with %s set(s).'%(n,len(sets))))
                        elif nError == 10:
                            feedback.reportError(QCoreApplication.translate('Interpretation Boundary',
                                                                            'Reached 10 errors and will stop reporting errors.'))
                        name = 'Errors'
                        s = 'Errors'
                except Exception as e:
                    feedback.reportError(QCoreApplication.translate('Interpretation Boundary', str(e)))
                    continue
            else:
                if gLen > 4 or gLen == 2:
                    nError += 1
                    if nError < 10:
                        feedback.reportError(QCoreApplication.translate('Interpretation Boundary', 'Error - found an intersection with %s nodes at %s. Consider repairing the dataset manually or use the repair topology tool.'%(gLen,n)))
                    elif nError == 10:
                        feedback.reportError(QCoreApplication.translate('Interpretation Boundary',
                                                                        'Reached 10 errors and will stop reporting errors.'))
                continue
            dataS.append(s)
            dataN.append(name)

        df2 = pd.DataFrame({'Sets': dataS, 'Name': dataN})
        del dataS,dataN

        df2['freq']=df2.groupby(by='Sets')['Sets'].transform('count')
        if dCountm > dCount:
            df2 = df2[(df2.freq > dCount) & (df2.freq < dCountm)]
        else:
            df2 = df2[df2.freq > dCount]

        sLen = len(df2.Sets.unique())
        if sLen == 0:
            feedback.reportError(QCoreApplication.translate('Error', 'No sets found to plot. Please check input parameters.'))
            return {}

        palette = cycle(px.colors.sequential.Reds)
        palette2 = cycle(px.colors.sequential.Blues)

        traces = []
        for n,g in df2.groupby('Name'):
            if 'abuts' in n:
                traces.append(go.Bar(y=[len(g)], x=['Y'], name=n,marker_color=next(palette)))
            elif 'cross-cut' in n:
                if len(g) > 0:
                    traces.append(go.Bar(y=[len(g)], x=['X'], name=n,marker_color=next(palette2)))
            else:
                traces.append(go.Bar(y=[len(g)], x=['Errors'], name=n, marker_color='#7f7f7f'))

        ngtPath = 'https://raw.githubusercontent.com/BjornNyberg/NetworkGT/master/Images/NetworkGT_Logo1.png'

        layout = go.Layout(images=[dict(source=ngtPath, xref="paper", yref="paper", x=1.0, y=1.0, sizex=0.2, sizey=0.2, xanchor="right",yanchor="bottom")],xaxis_title="Node Type",yaxis_title="Node Count")
        try:
            py.plot(traces, layout=layout, filename='relationships', auto_open=True)
        except Exception:
            fig.show(traces, layout=layout)

        return {}

