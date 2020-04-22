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

import os, math
from math import ceil
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsProcessingParameterField,QgsWkbTypes,QgsProcessingParameterBoolean, QgsFeature, QgsPointXY,QgsProcessingParameterNumber, QgsProcessing, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty)
from qgis.PyQt.QtGui import QIcon

class Fracture_Lines(QgsProcessingAlgorithm):

    Network='Network'
    Angle = 'Angle'
    Distance = 'Distance'
    Output = 'Output'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Define Fracture Lines"

    def tr(self, text):
        return QCoreApplication.translate("Define Fracture Lines", text)

    def displayName(self):
        return self.tr("Define Fracture Line Numbers")

    def group(self):
        return self.tr("1. Digitising")

    def shortHelpString(self):
        return self.tr("The tool will automatically define a fracture line number for a segmented fracture network at its intersections by calcualting grouping all connected branches that are within a given angle threshold. The 'Angle Threshold' defines the angle threshold at which a new fracture line number identifer will be created. Users can supply a 'Maximum Fracture Deflection' parameter to specify a distance to ignore the angle threshold if the following fracture line is within the angle threshold. \n Please refer to the help button for more information.")

    def groupId(self):
        return "1. Digitising"

    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/wiki/1.-Digitising-Tools"

    def createInstance(self):
        return type(self)()

    def icon(self):
        n,path = 2,os.path.dirname(__file__)
        while(n):
            path=os.path.dirname(path)
            n -=1
        pluginPath = os.path.join(path,'icons')
        return QIcon( os.path.join( pluginPath, 'N.jpg') )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Network"),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterNumber(
            self.Angle,
            self.tr("Angle Threshold"),
            QgsProcessingParameterNumber.Double,
            10.0,minValue=1.0))

        self.addParameter(QgsProcessingParameterNumber(
            self.Distance,
            self.tr("Maximum Fracture Deflection"),
            QgsProcessingParameterNumber.Double,
            0.0,minValue=0.0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.Output,
            self.tr("Output"),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback):

        try:
            import networkx as nx
        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            feedback.reportError(QCoreApplication.translate('Error',' '))
            feedback.reportError(QCoreApplication.translate('Error','Error loading modules - please install the necessary dependencies'))
            return {}

        layer = self.parameterAsLayer(parameters, self.Network, context)

        angle = parameters[self.Angle] #Orientation Threshold
        distance = parameters[self.Distance] #Distance Threshold

        fet = QgsFeature()
        fs = QgsFields()

        skip = ['Fault No']
        fields = layer.fields()
        for field in fields:
            if field.name() not in skip:
                fs.append( QgsField(field.name() ,field.type() ))

        fs.append(QgsField('Fault No', QVariant.Int))

        (writer, dest_id) = self.parameterAsSink(parameters, self.Output, context, fs, QgsWkbTypes.LineString, layer.sourceCrs())

        G = nx.Graph()
        P = 100000
        for feature in layer.getFeatures(QgsFeatureRequest()):
            try:
                try:
                    geom = feature.geometry().asPolyline()
                except Exception:
                    geom = feature.geometry().asMultiPolyline()[0]
                start,end = geom[0],geom[-1]
                startx,starty=start
                endx,endy=end
                branch = [(math.ceil(startx*P)/P,math.ceil(starty*P)/P),(math.ceil(endx*P)/P,math.ceil(endy*P)/P)]
                G.add_edge(branch[0],branch[1],weight=feature.geometry().length())

            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Node Error','%s'%(e)))

        feedback.pushInfo(QCoreApplication.translate('Create Lines','Calculating Fracture Line Numbers'))

        def calcOrient(start,end):
            startxC,startyC = start
            endxC,endyC = end
            dx,dy = endxC-startxC,endyC-startyC
            angle = math.degrees(math.atan2(dy,dx))
            bearing = (90.0 - angle) % 360
            return bearing

        data = {}
        enum = 0
        c = 5
        total = 100.0/len(G)
        for enum,node in enumerate(G.nodes()): #TO DO Simplify
            feedback.setProgress(int(enum*total))
            start = node
            prevOrient,end = None,None
            enum +=1
            origStart = start
            c = 1

            while start:
                c+=1
                edges = G.edges(start)
                orient,curStart,curEnd = None,None,None
                if c == 1000: #TO DO Fix Loop Break
                    None
                    break
                for edge in edges:
                    T = None
                    if edge[0] == start:
                        curEnd = edge[1]
                    else:
                        curEnd = edge[0]
                    line = (start,curEnd)
                    line2 = (curEnd,start)
                    if line in data or line2 in data:
                        continue
                    else:

                        if not prevOrient:
                            prevOrient = calcOrient(start,curEnd)
                            data[line]= enum
                            end = start
                            curStart = curEnd
                            origStart = start
                            keepOrient = prevOrient
                            break

                        curOrient = calcOrient(start,curEnd)
                        curDiff = 180 - abs(abs(prevOrient - curOrient) - 180)

                        if orient == None:
                            orient = curDiff + 1
                        if curDiff < orient:
                            if curDiff < angle or G.degree(start) == 2:
                                orient = curDiff
                                curStart = curEnd
                                keepOrient = curOrient
                orient2 = 1e10
                if curStart == None and prevOrient != None and distance > 0:
                    T = list(nx.dfs_edges(G, source=start, depth_limit=3))
                    G2 = nx.Graph()
                    G2.add_edges_from(T)

                    if start in G2:
                        path=nx.single_source_dijkstra_path(G2,start)

                        if start == origStart:
                            origOrient = prevOrient
                        else:
                            origOrient = calcOrient(origStart,start)

                        curD = None

                        for node2 in G2.nodes():
                            d = path[node2]
                            if len(d) < 3:
                                continue
                            else:
                                curOrient = calcOrient(d[1],d[-1])
                                curDiff = 180 - abs(abs(origOrient - curOrient) - 180)

                                if curDiff < angle and curDiff < orient2:
                                    dx,dy = (d[0][0]-d[1][0]),(d[0][1]-d[1][1])
                                    SP = math.sqrt((dx**2)+(dy**2))
                                    if SP < distance:
                                        orient2 = curDiff
                                        prevOrient = calcOrient(d[-1],d[-2])
                                        curD = d
                        if curD:
                            s,e = None,False
                            for p in curD:
                                if s == None:
                                    s = p
                                else:
                                    if (s,p) not in data:
                                        data[(s,p)] = enum
                                        data[(p,s)] = enum
                                        e = True
                                    s = p
                            if e:
                                start = curD[1]
                            else:
                                start = None

                        else:
                            start = None

                elif curStart:
                    if distance == 0:
                        prevOrient = keepOrient #calcOrient(origStart,curStart)
                    data[(start,curStart)]= enum
                    data[(curStart,start)]= enum
                    start = curStart
                    if origStart == start:
                        start = None
                else:
                    start = None

            origEnd = end
            c = 1
            while end:
                c+=1
                edges = G.edges(end)
                orient,curEnd = None,None
                if c == 1000:
                    end = None
                    break
                for edge in edges:
                    T = None
                    if edge[0] == end:
                        curStart = edge[1]
                    else:
                        curStart = edge[0]
                    line = (curStart,end)
                    line2 = (end,curStart)
                    if line in data or line2 in data:
                        continue
                    else:
                        if not prevOrient:
                            prevOrient = calcOrient(curStart,end)
                            data[line]= enum
                            curEnd = curStart
                            keepOrient = prevOrient
                            break
                        curOrient = calcOrient(curStart,end)
                        curDiff = 180 - abs(abs(prevOrient - curOrient) - 180)
                        if orient == None:
                            orient = curDiff + 1

                        if curDiff < orient:
                            if curDiff < angle or G.degree(end) == 2:
                                orient = curDiff
                                curEnd = curStart
                                keepOrient = curOrient

                orient2 = 1e10
                if curEnd == None and prevOrient != None and distance > 0:
                    T = list(nx.dfs_edges(G, source=end, depth_limit=3))
                    G2 = nx.Graph()
                    G2.add_edges_from(T)
                    if end in G2:
                        path=nx.single_source_dijkstra_path(G2,end)
                        if end == origStart:
                            origOrient = prevOrient
                        else:
                            origOrient = calcOrient(end,origEnd)

                        for node2 in G2.nodes():
                            d = path[node2]
                            if len(d) < 3:
                                continue
                            else:
                                curOrient = calcOrient(d[-1],d[1])
                                curDiff = 180 - abs(abs(origOrient - curOrient) - 180)

                                if curDiff < angle and curDiff < orient2:
                                    dx,dy = (d[0][0]-d[1][0]),(d[0][1]-d[1][1])
                                    SP = math.sqrt((dx**2)+(dy**2))
                                    if SP < distance:
                                        orient2 = curDiff
                                        prevOrient = calcOrient(d[-1],d[-2])
                                        curD = d
                        if curD:
                            s,e = None,False
                            for p in curD:
                                if s == None:
                                    s = p
                                else:
                                    if (s,p) not in data:
                                        data[(s,p)] = enum
                                        data[(p,s)] = enum
                                        e = True
                                    s = p

                            if e:
                                end = curD[1]

                            else:
                                end = None
                        else:
                            end = None

                elif curEnd:
                    if distance == 0:
                        prevOrient = keepOrient #calcOrient(curEnd,origEnd)
                    data[(curEnd,end)]= enum
                    data[(end,curEnd)]= enum
                    end = curEnd
                    if origEnd == end:
                        end = None
                else:
                    end = None

        total = layer.featureCount()
        total = 100.0/total
        feedback.pushInfo(QCoreApplication.translate('Create Lines','Creating New Feature Layer'))
        for enum2,feature in enumerate(layer.getFeatures(QgsFeatureRequest())):
            if total > 0:
                feedback.setProgress(int(enum2*total))
            try:
                geom = feature.geometry().asPolyline()
            except Exception:
                geom = feature.geometry().asMultiPolyline()[0]

            start,end = geom[0],geom[-1]
            startx,starty = (math.ceil(start[0]*P)/P,math.ceil(start[1]*P)/P)
            endx,endy = (math.ceil(end[0]*P)/P,math.ceil(end[1]*P)/P)

            FID=None
            line = ((startx,starty),(endx,endy))
            line2 = ((endx,endy),(startx,starty))
            if line in data:
                FID = data[line]
            elif line2 in data:
                FID = data[line2]
            else:
                enum +=1
                FID = enum

            rows = []
            for field in layer.fields():
                if field.name() not in skip:
                    rows.append(feature[field.name()])

            rows.append(FID)
            fet.setGeometry(feature.geometry())
            fet.setAttributes(rows)
            writer.addFeature(fet)

        return {}
