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

from collections import OrderedDict
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature, QgsRaster,QgsProcessingParameterBoolean, QgsPointXY, QgsSpatialIndex, QgsProcessingParameterRasterLayer, QgsProcessingParameterFolderDestination, QgsProcessingParameterField, QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsProcessingParameterNumber,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer)
from qgis.PyQt.QtGui import QIcon
import os,tempfile

class Tortuosity(QgsProcessingAlgorithm):

    Network = 'Fracture Network'
    Tortuosity ='Tortuosity Line'
    Weight = 'Weight Field'
    Sources = 'Source Points'
    Targets = 'Target Points'
    Deviation = 'Plot Deviation'
    Norm = 'Normalize Plot'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Tortuosity"

    def tr(self, text):
        return QCoreApplication.translate("Tortuosity", text)

    def displayName(self):
        return self.tr("Tortuosity")

    def group(self):
        return self.tr("3. Geometry")

    def shortHelpString(self):
        return self.tr("Measure the tortuosity between target and source points. Input requires a fracture network, a source point layer with a ID field and a corresponding target point layer with a ID field. If the 'Weight' option is supplied, the cost distance calculator will be weighted to the given field. \n Output will define a torutosity pathway for each ID from start to endpoint with corresponding information regarding its torutosity (angle of deflection / shortest distance to the endpoint) and deviation (distance of the tortuosity pathway from its shortest path of the line geometry).\n Please refer to the help button for more information.")

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
        return QIcon( os.path.join( pluginPath, 'T.jpg') )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Fracture Network"),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Sources,
            self.tr("Source Points"),
            [QgsProcessing.TypeVectorPoint]))

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Targets,
            self.tr("Target Points"),
            [QgsProcessing.TypeVectorPoint]))

        self.addParameter(QgsProcessingParameterField(self.Weight,
                                self.tr('Weight Field'), parentLayerParameterName=self.Network, type=QgsProcessingParameterField.Numeric, optional=True))

        self.addParameter(QgsProcessingParameterBoolean(self.Norm,
                    self.tr("Normalize Plot"),True))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.Tortuosity,
            self.tr("Tortuosity"),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback):

        try:
            import math, random, string
            import pandas as pd
            import processing as st
            import networkx as nx
            import numpy as np
        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            feedback.reportError(QCoreApplication.translate('Error',' '))
            feedback.reportError(QCoreApplication.translate('Error','Error loading modules - please install the necessary dependencies'))
            return {}


        plot = True

        try:
            import plotly.graph_objs as go
            import chart_studio.plotly as py
        except Exception:
            feedback.reportError(QCoreApplication.translate('Error','Plotting will be disabled as plotly module did not load - please install the necessary dependencies. '))
            plot = False

        Network = self.parameterAsLayer(parameters, self.Network, context)
        Sources = self.parameterAsLayer(parameters, self.Sources, context)
        Targets = self.parameterAsLayer(parameters, self.Targets, context)
        norm = parameters[self.Norm]

        Precision = 6

        explode = st.run("native:explodelines",{'INPUT':Network,'OUTPUT':'memory:'},context=context,feedback=feedback)

        wF = parameters[self.Weight]

        fet = QgsFeature()
        fs = QgsFields()

        skip = ['Value','Line','Deviation','Tort Index']
        fields = Network.fields()
        for field in fields:
            if field.name() not in skip:
                fs.append( QgsField(field.name() ,field.type() ))

        fs.append(QgsField('Value', QVariant.Double))
        fs.append(QgsField('Line', QVariant.String))
        fs.append(QgsField('Deviation', QVariant.Double))
        fs.append(QgsField('Tort Index', QVariant.Double))

        (writer, dest_id) = self.parameterAsSink(parameters, self.Tortuosity, context,
                                            fs, QgsWkbTypes.LineString, Network.sourceCrs())

        index = QgsSpatialIndex(explode['OUTPUT'].getFeatures())
        orig_data = {feature.id():feature for feature in explode['OUTPUT'].getFeatures()}

        srcs,tgts,data = {},{},{}

        field_check = Sources.fields().indexFromName('ID')

        if field_check == -1:
            feedback.reportError(QCoreApplication.translate('Error','No ID attribute in Source layer'))
            return {}

        field_check2 = Targets.fields().indexFromName('ID')
        if field_check2 == -1:
            feedback.reportError(QCoreApplication.translate('Error','No ID attribute in Targets layer'))
            return {}

        feedback.pushInfo(QCoreApplication.translate('Model','Defining Source Nodes'))
        total = 100.0/Sources.featureCount()
        c = 0
        for enum,feature in enumerate(Sources.getFeatures()): #Find source node
            try:
                if total > 0:
                    feedback.setProgress(int(enum*total))
                pnt = feature.geometry().asPoint()

                startx,starty = (round(pnt.x(),Precision),round(pnt.y(),Precision))

                featFIDs = index.nearestNeighbor(QgsPointXY(startx,starty), 2)

                d = 1e10
                for FID in featFIDs:
                    feature2 = orig_data[FID]
                    testGeom = QgsGeometry.fromPointXY(QgsPointXY(startx,starty))
                    dist = QgsGeometry.distance(testGeom,feature2.geometry())

                    if dist < d: #Find closest vertex in graph to source point

                        ID = feature['ID']
                        d = dist
                        geom = feature2.geometry()

                        start,end = geom.asPolyline()

                        startx2,starty2 = (round(start.x(),Precision),round(start.y(),Precision))
                        endx2,endy2 = (round(end.x(),Precision),round(end.y(),Precision))

                        testGeom2 = QgsGeometry.fromPointXY(QgsPointXY(startx2,starty2))
                        testGeom3 = QgsGeometry.fromPointXY(QgsPointXY(endx2,endy2))
                        near = QgsGeometry.distance(testGeom2,testGeom)
                        near2 = QgsGeometry.distance(testGeom3,testGeom)
                        if near < near2:
                            x,y = startx2,starty2
                        else:
                            x,y = endx2,endy2
                if ID in srcs:
                    srcs[ID].append((x,y))
                else:
                    srcs[ID] = [(x,y)]
                c+=1

            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))

        if Targets:
            total = 100.0/Targets.featureCount()

            feedback.pushInfo(QCoreApplication.translate('Model','Defining Target Nodes'))
            for enum,feature in enumerate(Targets.getFeatures()): #Find source node
                try:
                    if total > 0:
                        feedback.setProgress(int(enum*total))
                    pnt = feature.geometry().asPoint()

                    startx,starty = (round(pnt.x(),Precision),round(pnt.y(),Precision))

                    featFIDs = index.nearestNeighbor(QgsPointXY(startx,starty), 2)

                    d = 1e10
                    for FID in featFIDs:
                        feature2 = orig_data[FID]
                        testGeom = QgsGeometry.fromPointXY(QgsPointXY(startx,starty))
                        dist = QgsGeometry.distance(testGeom,feature2.geometry())

                        if dist < d: #Find closest vertex in graph to source point
                            ID = feature['ID']
                            d = dist
                            geom = feature2.geometry()

                            start,end = geom.asPolyline()

                            startx2,starty2 = (round(start.x(),Precision),round(start.y(),Precision))
                            endx2,endy2 = (round(end.x(),Precision),round(end.y(),Precision))

                            testGeom2 = QgsGeometry.fromPointXY(QgsPointXY(startx2,starty2))
                            testGeom3 = QgsGeometry.fromPointXY(QgsPointXY(endx2,endy2))
                            near = QgsGeometry.distance(testGeom2,testGeom)
                            near2 = QgsGeometry.distance(testGeom3,testGeom)
                            if near < near2:
                                x,y = startx2,starty2
                            else:
                                x,y = endx2,endy2
                    if ID in tgts:
                        tgts[ID].append((x,y))
                    else:
                        tgts[ID] = [(x,y)]
                    c+=1

                except Exception as e:
                    feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))

        total = 100.0/Network.featureCount()

        G = nx.Graph()

        feedback.pushInfo(QCoreApplication.translate('Model','Building Graph'))
        for enum,feature in enumerate(explode['OUTPUT'].getFeatures()): #Build Graph
            try:
                if total > 0:
                    feedback.setProgress(int(enum*total))

                geom = feature.geometry()
                if geom.isMultipart():
                    start,end = geom.asMultiPolyline()[0]
                else:
                    start,end = geom.asPolyline()

                startx,starty = (round(start.x(),Precision),round(start.y(),Precision))
                endx,endy = (round(end.x(),Precision),round(end.y(),Precision))

                if wF:
                    w = feature[wF]
                    if type(w) == int or type(w) == float:
                        pass
                    else:
                        feedback.reportError(QCoreApplication.translate('Error','Weight field contains non numeric values - check for null values'))
                        return {}
                    w = float(W)*feature.geometry().length()
                else:
                    w = feature.geometry().length()

                G.add_edge((startx,starty),(endx,endy),weight=w)
                #G.add_edge((endx,endy),(startx,starty),weight=w)

                rows = []
                for field in fields:
                    if field.name() not in skip:
                        rows.append(feature[field.name()])
                data[((endx,endy),(startx,starty))] = rows

            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))

        def Deviation (start,end,m,midx,midy): #Calculate centerline deviation

            u = ((midx - start.x()) * (end.x() - start.x()) + (midy - start.y()) * (end.y() - start.y()))/m
            x = start.x() + u * (end.x() - start.x())
            y = start.y() + u * (end.y() - start.y())
            d = ((end.x()-start.x())*(midy-start.y()) - (end.y() - start.y())*(midx - start.x()))
            dx = start.x() - end.x()
            dy =  start.y() - end.y()
            shortestPath = math.sqrt((dx**2)+(dy**2))

            dx = start.x() - x
            dy =  start.y() - y
            shortestPath1 = math.sqrt((dx**2)+(dy**2))

            if shortestPath < shortestPath1:
                sym = QgsGeometry.fromPolylineXY([QgsPointXY(end.x(),end.y()),QgsPointXY(midx,midy)])
            else:
                sym = QgsGeometry.fromPolylineXY([QgsPointXY(x,y),QgsPointXY(midx,midy)])

            symL = sym.length()
            if d < 0:
                DW = -(symL)
            else:
                DW = symL
            return DW

        SN,Lens,DD,T = [],[],[],{}

        feedback.pushInfo(QCoreApplication.translate('Model','Creating Fracture Network'))
        try:
            c2 = 0
            if len(srcs) > 0:
                total = 100.0/c
                for FID in srcs:
                    sources = srcs[FID]
                    for source in sources:
                        if G.has_node(source):
                            if FID in tgts:
                                targets = tgts[FID]
                                for target in targets:
                                    c2+= 1
                                    feedback.setProgress(int(c2*total))
                                    try:
                                        path = nx.dijkstra_path(G,source,target)
                                    except Exception:
                                        feedback.reportError(QCoreApplication.translate('Error','No connection found between source and target of ID %s'%(FID)))
                                        continue

                                    G2 = G.subgraph(path)

                                    lengths = nx.single_source_dijkstra_path_length(G2,source)

                                    start = max(lengths,key=lengths.get)
                                    end = min(lengths,key=lengths.get)

                                    start,end = QgsPointXY(start[0],start[1]),QgsPointXY(end[0],end[1])

                                    m = start.sqrDist(end)

                                    dx,dy = end[0]-start[0],end[1]-start[1]
                                    SP_Len = math.sqrt((dx**2)+(dy**2))
                                    l = 0
                                    for edge in G2.edges():
                                        L = -9999

                                        for node in edge:

                                            if node in lengths:
                                                dist = lengths[node]

                                                if L == -9999:
                                                    L = dist
                                                    prev = node

                                                elif dist < L:
                                                    L = dist
                                                    midS = node
                                                    midE = prev

                                                else:
                                                    midS = prev
                                                    midE = node

                                        if L != -9999: # Check if there is a connection

                                            if (edge[1],edge[0]) in data:
                                                rows = data[(edge[1],edge[0])]
                                            else:
                                                rows = data[(edge[0],edge[1])]

                                            midEx,midEy = midE
                                            midSx,midSy = midS
                                            points = [QgsPointXY(midSx,midSy),QgsPointXY(midEx,midEy)]


                                            DW = Deviation(start,end,m,midEx,midEy)
                                            #DW2 = Deviation(start,end,m,midSx,midSy)
                                            outGeom = QgsGeometry.fromPolylineXY(points)
                                            fet.setGeometry(outGeom)

                                            dx,dy = midSx-start[0],midSy-start[1]
                                            SP = math.sqrt((dx**2)+(dy**2))

                                            dx,dy = midEx-start[0],midEy-start[1]
                                            SP2 = math.sqrt((dx**2)+(dy**2))

                                            tort = SP2 - (SP - outGeom.length())

                                            rows.extend([float(L),str(c2),float(DW),tort])

                                            SN.append(c2)
                                            Lens.append(float(L))
                                            DD.append(tort)

                                            l += outGeom.length()
                                            fet.setAttributes(rows)
                                            writer.addFeature(fet)
                                    T[c2] = SP_Len / float(l)
                            else:
                                feedback.reportError(QCoreApplication.translate('Model','Source FID %s has no targets'%(FID)))

        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))

        if plot:
            feedback.pushInfo(QCoreApplication.translate('Model','Plotting Data'))
            data,vf_values = {},{}
            df = pd.DataFrame({0:SN, 1:Lens, 2:DD})
            traces = []

            for n,d in df.groupby(0):

                if len(d) > 1:

                    x,y,c = [0],[0],0.0
                    values = d.sort_values(1)

                    prev = 0
                    for x_value,disp in zip(values[1],values[2]):
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

                    sum_length = max(y)
                    sum_dist = max(x)

                    m = float(sum_length/sum_dist)

                    for x_v,y_v in zip(x,y):
                        test_y = x_v*m
                        vf = [y_v/float(y[-1]) - test_y/float(y[-1])]
                        if n in vf_values:
                            vf_data = vf_values[n]
                            vf_data += vf
                            vf_values[n] = vf_data
                        else:
                            vf_values[n] = vf
                    if norm:
                        x= [n/max(x) for n in x]
                        y = [n/max(y) for n in y]
                    traces.append(go.Scatter(
                                        x = x,
                                        y = y,
                                        mode = 'lines',
                                        name = n,
                                        xaxis='x1',
                                        yaxis='y1'
                                    )
                            )

            data = OrderedDict(sorted(data.items()))
            table_vals = [[],[],[],[],[],[],[],[],[],[],[],[],[],[]]

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

            for k,t in T.items():
                table_vals[10].append(round(t,4))

            for k,vf in vf_values.items():
                table_vals[11].append(round(max(vf),2))
                table_vals[12].append(round(min(vf),2))
                table_vals[13].append(round(math.fabs(max(vf))+ math.fabs(min(vf)),2))

            col_labels = ['Sample No','Count','mean','std','min','25%','50%','75%','Max','CoV','Tortuosity',r'D+',r'D-','Vf']
            cols = [['<b>%s</b>'%(col)]for col in col_labels]

            axis=dict(
                showline=True,
                zeroline=False,
                showgrid=True,
                mirror=True,
                ticklen=2,
                gridcolor='#ffffff',
                tickfont=dict(size=10)
            )

            traces.append(go.Table(
                domain=dict(x=[0.0, 1.0],
                            y=[0.0, 0.2]),
                columnwidth = [1, 2, 2, 2],
                columnorder=np.arange(0,14,1),
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
            ngtPath = 'https://raw.githubusercontent.com/BjornNyberg/NetworkGT/master/Images/NetworkGT_Logo1.png'
            layout= go.Layout(images=[dict(source=ngtPath,xref="paper", yref="paper", x=1.0, y=1.0,sizex=0.2, sizey=0.2, xanchor="right", yanchor="bottom")],
                title= 'Tortuosity Plot',
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
                    title= 'Cumulative Value',
                    ticklen= 5,
                    gridwidth= 2,
                    **dict(domain=[0.3, 1], anchor='x1')
                ),

                showlegend= True
            )
            fig = go.Figure(traces, layout=layout)
            try:
                py.plot(fig, filename='Tortuosity', auto_open=True)
            except Exception:
                fig.show()

        return {self.Tortuosity:dest_id}
