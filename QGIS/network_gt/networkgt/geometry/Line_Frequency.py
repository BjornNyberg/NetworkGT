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
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature, QgsPointXY,QgsSpatialIndex,QgsProcessingParameterBoolean, QgsProcessingParameterFolderDestination, QgsProcessingParameterField, QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsProcessingParameterNumber,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer)
from qgis.PyQt.QtGui import QIcon

class LineFrequency(QgsProcessingAlgorithm):

    LG = 'Line Grid'
    Network = 'Fracture Network'
    Weight = 'Weight Field'
    Group = "Groupby Field"
    Norm = 'Normalize'
    Combine = 'Combine Graphs'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Line Frequency"

    def tr(self, text):
        return QCoreApplication.translate("Line Frequency", text)

    def displayName(self):
        return self.tr("Line Frequency")

    def group(self):
        return self.tr("3. Geometry")

    def shortHelpString(self):
        return self.tr("Plots cumulative fracture frequency against distance along a line sample. The user has the option to weight frequency by a fracture attribute (e.g. aperture, displacement etc.) and group the fracture data (e.g. by orientation set number). \n The inputs are a fracture network linestring and a line sample/line grid linestring. The tool outputs a cumulative frequency line plot in an external browser window. An additional table quantifes the spatial heterogeneity (V) of the fracture frequencies by comparing their cumulative line plot with a uniform distribution and summing its maximum (D+) and minimum (D-) deviations from that uniform distribution. \n N.B. To avoid orientaiton bias it is highly recommended that the user applies this analysis to a line sample that is approximately perpendicular to the fracture population of interest.\n Please refer to the help button for more information.")

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

        return QIcon( os.path.join( pluginPath, 'LF.jpg') )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.LG,
            self.tr("Line Grid"),
            [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Fracture Network"),
            [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterField(self.Weight,
                                self.tr('Weight Field'), parentLayerParameterName=self.Network, type=QgsProcessingParameterField.Numeric, optional=True))
        self.addParameter(QgsProcessingParameterField(self.Group,
                                self.tr('Group Field'), parentLayerParameterName=self.Network, type=QgsProcessingParameterField.Any, optional=True))
        self.addParameter(QgsProcessingParameterBoolean(self.Norm,
                    self.tr("Normalize"),False))
        self.addParameter(QgsProcessingParameterBoolean(self.Combine,
                    self.tr("Combine Plots"),False))

    def processAlgorithm(self, parameters, context, feedback):

        try:
            import os, math, string, random
            import processing as st
            import networkx as nx
            import numpy as np
            import plotly.graph_objs as go
            import pandas as pd
            from math import ceil

        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            feedback.reportError(QCoreApplication.translate('Error',' '))
            feedback.reportError(QCoreApplication.translate('Error','Error loading modules - please install the necessary dependencies'))
            return {}

        LG = self.parameterAsSource(parameters, self.LG, context)
        Network = self.parameterAsSource(parameters, self.Network, context)
        Norm = parameters[self.Norm]
        Combine = parameters[self.Combine]

        field_check = LG.fields().indexFromName('Sample_No_')

        if field_check == -1:
            editLayer = self.parameterAsLayer(parameters, self.LG, context)
            pr = editLayer.dataProvider()
            pr.addAttributes([QgsField('Sample_No_', QVariant.Int)])
            editLayer.updateFields()
            f_len = len(editLayer.fields()) - 1
            editLayer.startEditing()
            for feature in editLayer.getFeatures():
                pr.changeAttributeValues({feature.id():{f_len:feature.id()}})
            editLayer.commitChanges()

        wF = parameters[self.Weight]
        gF = parameters[self.Group]

        index = QgsSpatialIndex(Network.getFeatures())
        orig_data = {feature.id():feature for feature in Network.getFeatures()}

        infc = parameters[self.LG]
        infc2 = parameters[self.Network]

        P = 100000
        sources,edges,Lengths = {},{},{}
        for feature in LG.getFeatures():
            geom = feature.geometry()
            if QgsWkbTypes.isSingleType(geom.wkbType()):
                geom = geom.asPolyline()
            else:
                geom = geom.asMultiPolyline()[0]
            x,y = geom[0]
            startx,starty=ceil(x*P)/P,ceil(y*P)/P
            sources[feature['Sample_No_']] = (startx,starty)

        feedback.pushInfo(QCoreApplication.translate('TempFiles','Creating Line Frequency Sampling'))
        parameters = {'INPUT':infc,'LINES':infc2,'OUTPUT':'memory:'}
        templines = st.run('native:splitwithlines',parameters,context=context,feedback=feedback)

        for feature in templines['OUTPUT'].getFeatures():
            geom = feature.geometry()
            if QgsWkbTypes.isSingleType(geom.wkbType()):
                geom = geom.asPolyline()
            else:
                geom = geom.asMultiPolyline()[0]
            start,end = geom[0],geom[-1]
            startx,starty=start
            endx,endy=end

            pnts1,pnts2 = [(ceil(startx*P)/P,ceil(starty*P)/P),(ceil(endx*P)/P,ceil(endy*P)/P)]
            Length = feature.geometry().length()
            ID = feature['Sample_No_']

            if ID in edges:
                edges[ID].add_edge(pnts1,pnts2,weight=Length)
            else:
                G = nx.Graph()
                G.add_edge(pnts1,pnts2,weight=Length)
                edges[ID] = G

        SN, SS, D, W = [],[],[],[]
        for feature in templines['OUTPUT'].getFeatures():
            geom = feature.geometry()
            if QgsWkbTypes.isSingleType(geom.wkbType()):
                geom = geom.asPolyline()
            else:
                geom = geom.asMultiPolyline()[0]
            start,end = geom[0],geom[-1]
            startx,starty=start
            endx,endy=end

            startx,starty = (ceil(startx*P)/P,ceil(starty*P)/P)
            endx, endy = (ceil(endx*P)/P,ceil(endy*P)/P)

            ID = feature['Sample_No_']

            if ID not in Lengths:
                G = edges[ID]
                if len(G.nodes()) > 2:
                    source = sources[ID]
                    length,path = nx.single_source_dijkstra(G,source,weight='weight')
                    Lengths[ID] = length

            if ID in Lengths:
                L = Lengths[ID][(endx,endy)]

                if gF != None or wF != None:
                    featFIDs = index.nearestNeighbor(QgsPointXY(endx,endy), 2)

                    for FID in featFIDs:
                        feature2 = orig_data[FID]
                        testGeom = QgsGeometry.fromPointXY(QgsPointXY(endx,endy))
                        wFv = 0
                        gFv = 'Total'
                        if testGeom.buffer(0.001,5).intersects(feature2.geometry()):
                            if wF:
                                wFv = feature2[wF]
                                if type(wFv) == int or type(wFv) == float:
                                    pass
                                else:
                                    feedback.reportError(QCoreApplication.translate('Error','Weight field contains non numeric values - check for null values'))
                                    return {}
                            if gF:
                                gFv = feature2[gF]
                            break

                SN.append(ID)
                D.append(L)
                if gF:
                    SS.append(str(gFv))
                else:
                    SS.append('Total')
                if wF:
                    W.append(float(wFv))
                else:
                    W.append(1)


        del sources,edges,Lengths

        data2 = pd.DataFrame({0:SN, 1:SS, 2:D, 3:W})
        data2.dropna(inplace=True)

        col_labels = ['Sample No','Count','mean','std','min','25%','50%','75%','Max','CoV',r'D+',r'D-','Vf']
        cols = [['<b>%s</b>'%(col)]for col in col_labels]
        ngtPath = 'https://raw.githubusercontent.com/BjornNyberg/NetworkGT/master/Images/NetworkGT_Logo1.png'
        axis=dict(
            showline=True,
            zeroline=False,
            showgrid=True,
            mirror=True,
            ticklen=2,
            gridcolor='#ffffff',
            tickfont=dict(size=10)
        )

        layout= go.Layout(images=[dict(source=ngtPath,xref="paper", yref="paper", x=1.0, y=1.0,sizex=0.2, sizey=0.2, xanchor="right", yanchor="bottom")],
            title= 'Line Frequency Plot',
            margin = dict(t=100),
            xaxis1= dict(
                axis,
                title= 'Distance',
                ticklen= 5,
                gridwidth= 2,
                **dict(domain=[0, 1], anchor='y1')
            ),
            yaxis1=dict(
                axis,
                title= 'Frequency',
                ticklen= 5,
                gridwidth= 2,
                **dict(domain=[0.3, 1], anchor='x1')
            ),

            showlegend= True
        )

        table_vals = [[],[],[],[],[],[],[],[],[],[],[],[],[]]
        data,vf_values = {},{}
        traces = []

        for n,df in data2.groupby(0):
            if len(df) > 1:
                if not Combine:
                    table_vals = [[],[],[],[],[],[],[],[],[],[],[],[],[]]
                    data,vf_values = {},{}
                    traces = []

                max_dist = max(df[2])

                x,y,c = [0],[0],0.0
                values = df.sort_values(2)
                values.iloc[-1, values.columns.get_loc(3)] = 0

                prev = 0
                for x_value,disp in zip(values[2],values[3]):
                    y.append(y[-1])
                    c += disp
                    y.append(c)
                    x.extend([x_value,x_value])
                    spacing = [x_value - prev]
                    prev = x_value

                    if n not in data:
                        data[n] = spacing
                    else:
                        spacing_data = data[n]
                        spacing += spacing_data
                        data[n] = spacing

                m = float(max(y)/max_dist)

                for x_v,y_v in zip(x,y):
                    test_y = x_v*m
                    vf = [y_v/float(y[-1]) - test_y/y[-1]]
                    if n in vf_values:
                        vf_data = vf_values[n]
                        vf_data += vf
                        vf_values[n] = vf_data
                    else:
                        vf_values[n] = vf
                if Norm:
                    xmax = max(x)
                    ymax = max(y)
                    x = [v/xmax for v in x]
                    y = [v/ymax for v in y]

                traces.append(go.Scatter(
                                    x = x,
                                    y = y,
                                    mode = 'lines',
                                    name = n,
                                    xaxis='x1',
                                    yaxis='y1'
                                ))

                for n2V,g in df.groupby(1):
                    n2 = 'Sample %s - %s'%(n,n2V)
                    if n2V == 'Total':
                        continue
                    else:
                        x,y,c = [0],[0],0.0
                        values = g.sort_values(2)

                        prev = 0
                        for x_value,disp in zip(values[2],values[3]):

                            y.append(y[-1])
                            c += disp
                            y.append(c)
                            x.extend([x_value,x_value])
                            spacing = [x_value - prev]

                            prev = x_value

                            if n2 not in data:
                                data[n2] = spacing

                            else:
                                spacing_data = data[n2]
                                spacing += spacing_data
                                data[n2] = spacing


                        x.append(max_dist)
                        y.append(y[-1])

                        spacing_data = data[n2]
                        spacing = [max_dist - prev]
                        spacing += spacing_data
                        data[n2] = spacing

                        m = float(max(y)/max_dist)
                        for x_v,y_v in zip(x,y):
                            test_y = x_v*m
                            vf = [y_v/float(y[-1]) - test_y/float(y[-1])]

                            if n2 in vf_values:
                                vf_data = vf_values[n2]
                                vf_data += vf
                                vf_values[n2] = vf_data
                            else:
                                vf_values[n2] = vf

                        if Norm:
                            xmax = max(x)
                            ymax = max(y)
                            x = [v/xmax for v in x]
                            y = [v/ymax for v in y]

                        traces.append(go.Scatter(
                                    x = x,
                                    y = y,
                                    mode = 'lines',
                                    name = n2,
                                    xaxis='x1',
                                    yaxis='y1'
                                ))
            if not Combine:
                if not data:
                    continue

                for k,v in data.items():
                    table_vals[0].append(str(k))
                    table_vals[1].append(len(v))
                    table_vals[2].append(round(np.mean(v),2))
                    table_vals[3].append(round(np.std(v),2))
                    table_vals[4].append(round(min(v),2))
                    table_vals[5].append(round(np.percentile(v, 25),2))
                    table_vals[6].append(round(np.percentile(v, 50),2))
                    table_vals[7].append(round(np.percentile(v, 75),2))
                    table_vals[8].append(round(max(v),2))
                    table_vals[9].append(round(np.std(v)/np.mean(v),2))

                for k,vf in vf_values.items():
                    table_vals[10].append(round(max(vf),2))
                    table_vals[11].append(round(min(vf),2))
                    table_vals[12].append(round(math.fabs(max(vf))+ math.fabs(min(vf)),2))

                traces.append(go.Table(
                    domain=dict(x=[0.0, 1.0],
                                y=[0.0, 0.2]),
                    columnwidth = [1, 2, 2, 2],
                    columnorder=np.arange(0,13,1),
                    header = dict(height = 25,
                                  values = cols,
                                  line = dict(color='rgb(50, 50, 50)'),
                                  align = ['left'] * 10,
                                  font = dict(color=['rgb(45, 45, 45)'] * 5, size=14),
                                  fill = dict(color='#d562be')),

                    cells = dict(values = table_vals,
                                 line = dict(color='#506784'),
                                 align = ['left'] * 10,
                                 font = dict(color=['rgb(40, 40, 40)'] * 5, size=12),
                                 format = [None]+[".2f"]*12,
                                 height = 50,
                                 fill = dict(color=['rgb(235, 193, 238)', 'rgba(228, 222, 249, 0.65)']))))

                fig = dict(data=traces, layout=layout)
                fig.show()

        if Combine:

            for k,v in data.items():
                table_vals[0].append(str(k))
                table_vals[1].append(len(v))
                table_vals[2].append(round(np.mean(v),2))
                table_vals[3].append(round(np.std(v),2))
                table_vals[4].append(round(min(v),2))
                table_vals[5].append(round(np.percentile(v, 25),2))
                table_vals[6].append(round(np.percentile(v, 50),2))
                table_vals[7].append(round(np.percentile(v, 75),2))
                table_vals[8].append(round(max(v),2))
                table_vals[9].append(round(np.std(v)/np.mean(v),2))

            for k,vf in vf_values.items():
                table_vals[10].append(round(max(vf),2))
                table_vals[11].append(round(min(vf),2))
                table_vals[12].append(round(math.fabs(max(vf))+ math.fabs(min(vf)),2))

            traces.append(go.Table(
                domain=dict(x=[0.0, 1.0],
                            y=[0.0, 0.2]),
                columnwidth = [1, 2, 2, 2],
                columnorder=np.arange(0,13,1),
                header = dict(height = 25,
                              values = cols,
                              line = dict(color='rgb(50, 50, 50)'),
                              align = ['left'] * 10,
                              font = dict(color=['rgb(45, 45, 45)'] * 5, size=14),
                              fill = dict(color='#d562be')),

                cells = dict(values = table_vals,
                             line = dict(color='#506784'),
                             align = ['left'] * 10,
                             font = dict(color=['rgb(40, 40, 40)'] * 5, size=12),
                             format = [None]+[".2f"]*12,
                             height = 50,
                             fill = dict(color=['rgb(235, 193, 238)', 'rgba(228, 222, 249, 0.65)']))))

            fig = dict(data=traces, layout=layout)
            fig.show()

        return {}
