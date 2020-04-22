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
import processing as st
import itertools
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProcessingParameterDefinition,QgsField,QgsVectorFileWriter,QgsVectorLayer,QgsMultiLineString,QgsProcessingParameterField,QgsProcessingParameterBoolean, QgsFeature, QgsPointXY,QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry,QgsSpatialIndex, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty)
from qgis.PyQt.QtGui import QIcon

class SnapYNodes(QgsProcessingAlgorithm):

    Network='Network'
    Snap='Connect Y Nodes'
    Distance = 'Distance'
    Angle = 'Angle'
    iters = 'Distance Iterations'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Connect Y Nodes"

    def tr(self, text):
        return QCoreApplication.translate("Connect Y Nodes", text)

    def displayName(self):
        return self.tr("Connect Y Nodes")

    def group(self):
        return self.tr("1. Digitising")

    def shortHelpString(self):
        return self.tr("Snap two Y nodes within a given distance and angle to create an X node. 'Distance to Snap' specifies the search distance to connect two Y nodes. The 'Angle to Snap' defines the angle difference allowed between the two linestring geometries to be snapped. \n'Number of Distance Iterations' specifies the number of search distance iterations to perform as 'Distance to Snap' / 'Number of Distance Iterations'. The tool will snap to the first linestring geometry that meets the thresholds provided based on the order in the attribute table.\n Please refer to the help button for more information.")

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
        return QIcon( os.path.join( pluginPath, 'Ynode.jpg') )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Network"),
            [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.Snap,
            self.tr("Snap Y Nodes"),
            QgsProcessing.TypeVectorLine))
        self.addParameter(QgsProcessingParameterNumber(
            self.Distance,
            self.tr("Distance to Snap"),
            QgsProcessingParameterNumber.Double,
            0.5,minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.Angle,
            self.tr("Angle to Snap"),
            QgsProcessingParameterNumber.Double,
            15.0,minValue=1.0))

        param1 = QgsProcessingParameterNumber(self.iters,
                                self.tr('Number of Distance Iterations'), QgsProcessingParameterNumber.Integer,1,minValue=1)

        param1.setFlags(param1.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param1)

    def processAlgorithm(self, parameters, context, feedback):

        try:
            import networkx as nx
        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            feedback.reportError(QCoreApplication.translate('Error',' '))
            feedback.reportError(QCoreApplication.translate('Error','Error loading modules - please install the necessary dependencies'))
            return {}

        layer = self.parameterAsLayer(parameters, self.Network, context)

        d = parameters[self.Distance]
        a = parameters[self.Angle]
        i = parameters[self.iters]

        #TO DO - Check if repair is needed
        params = {'Network':layer,'Output':'memory:','V Node Distance':0,'V Node Angle':0,'Create X Nodes':False,'Remove Circles':False,'Multiple Intersections':False}
        repaired = st.run("NetworkGT:Repair Topology",params,context=context,feedback=None) #Repair potential V nodes

        G = nx.MultiGraph() #Store all node connections

        features = repaired['Output'].getFeatures(QgsFeatureRequest())

        fields = QgsFields()
        for field in layer.fields():
            fields.append(QgsField(field.name(),field.type()))

        (writer, dest_id) = self.parameterAsSink(parameters, self.Snap, context,
                                               fields, QgsWkbTypes.LineString, layer.sourceCrs())
        total = layer.featureCount()
        total = 100.0/total
        for enum,feature in enumerate(features):
            try:
                if total > 0:
                    feedback.setProgress(int(enum*total))
                geom = feature.geometry().asPolyline()
                start,end = geom[0],geom[-1]
                startx,starty=start
                endx,endy=end
                length = feature.geometry().length()
                branch = [(startx,starty),(endx,endy)]
                G.add_edge(branch[0],branch[1],weight=length)
            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Node Error','%s'%(e)))

        def orientation(start,end):
            startx,starty = start
            endx,endy = end
            dx = endx - startx
            dy =  endy - starty
            angle = math.degrees(math.atan2(dy,dx))
            bearing = (90.0 - angle) % 360
            bearing = round(bearing,2)
            return bearing

        feedback.pushInfo(QCoreApplication.translate('Create Lines','Snapping Y Nodes'))

        skip,skip_edges = [],[]
        outEdges = {}
        v = d/i
        curD = 0
        total = 100.0/i
        for enum in range(i): #TO DO remove iterative distance search
            curD += v
            feedback.setProgress(int(enum*total))
            for node in G.nodes():

                if G.degree(node) == 3:

                    try:
                        if node in skip:
                            continue

                        edges = G.edges(node,data=True)
                        orient = []
                        orients = {}
                        for edge in edges: #Find orientation of edges
                            if edge[0] == node:
                                curOrient = orientation(edge[1],node)
                            else:
                                curOrient = orientation(edge[0],node)
                            if curOrient >= 180:
                                curOrient -= 180
                            orient.append(curOrient)
                        if len(orient) == 0:
                            continue
                        for o1,o2 in itertools.combinations(orient,2): #Find lowest angle
                            curDiff = 180 - abs(abs(o1 - o2) - 180)
                            orients[curDiff] = [o1,o2]
                        if len(orients) == 0:
                            continue
                        orientPar = orients[min(orients.keys())]
                        orientPer = min([o for o in orient if o not in orientPar])

                        for edge in edges: #Find start point of perpendicular line
                            if edge[0] == node:
                                curOrient = orientation(edge[1],node)
                                start = edge[1]
                            else:
                                curOrient = orientation(edge[0],node)
                                start = edge[0]
                            if curOrient >= 180:
                                curOrient -= 180
                            if curOrient == orientPer:
                                orientPer = orientation(start,node)
                                break

                        diff,curDist = 360,1e10
                        for edge in edges:
                            node2 = None
                            dist = edge[2]['weight']
                            if dist > curD:
                                continue
                            if edge[0] == node:
                                curOrient = orientation(edge[1],node)
                            else:
                                curOrient = orientation(edge[0],node)
                            if curOrient >= 180:
                                curOrient -= 180
                            if curOrient in orientPar:
                                if edge[0] != node and edge[0] not in skip and G.degree(edge[0]) == 3:
                                    edges2 = G.edges(edge[0])
                                    node2 = edge[0]
                                elif edge[1] != node and G.degree(edge[1]) == 3 and edge[1] not in skip:
                                    edges2 = G.edges(edge[1])
                                    node2 = edge[1]
                                if node2:
                                    for edge2 in edges2:
                                        if edge2[0] == node2:
                                            curOrient2 = orientation(node2,edge2[1])
                                        else:
                                            curOrient2 = orientation(node2,edge2[0])

                                        curDiff = 180 - abs(abs(orientPer - curOrient2) - 180)

                                        if curDiff < a and curDiff < diff and dist < curDist: #Find closest orientation to parallel line
                                            diff = curDiff
                                            curDist = dist
                                            curPoint = node2

                            if diff != 360:
                                if node not in skip and curPoint not in skip: #TO DO update node count of Graph
                                    outEdges[curPoint] = node
                                    skip_edges.extend([(node,curPoint),(curPoint,node)])
                                    skip.append(curPoint)
                                    skip.append(node)

                    except Exception as e:
                        feedback.pushInfo(QCoreApplication.translate('Create Lines','%s'%(e)))
                        continue

        fet = QgsFeature()

        for feature in repaired['Output'].getFeatures(QgsFeatureRequest()):
            try:
                geom = feature.geometry().asPolyline()
                start,end = geom[0],geom[-1]
                startx,starty = start
                endx,endy = end
                if ((startx,starty),(endx,endy)) in skip_edges:
                    continue
                if (startx,starty) in outEdges:
                    node = outEdges[(startx,starty)]
                    geom = geom[1:]
                    geom.insert(0,QgsPointXY(node[0],node[1]))
                if (endx,endy) in outEdges:
                    node = outEdges[(endx,endy)]
                    geom = geom[:-1]
                    geom.append(QgsPointXY(node[0],node[1]))

                rows = []
                for field in layer.fields():
                    rows.append(feature[field.name()])
                fet.setAttributes(rows)
                outGeom = QgsGeometry.fromPolylineXY(geom)
                fet.setGeometry(outGeom)
                writer.addFeature(fet,QgsFeatureSink.FastInsert)
            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Node Error','%s'%(e)))

        return {self.Snap:dest_id}
