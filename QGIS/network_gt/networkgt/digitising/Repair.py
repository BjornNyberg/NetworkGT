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
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessingParameterDefinition,QgsField,QgsVectorFileWriter,QgsVectorLayer,QgsMultiLineString,QgsProcessingParameterField,QgsProcessingParameterBoolean, QgsFeature, QgsPointXY,QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry,QgsSpatialIndex, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty)
from qgis.PyQt.QtGui import QIcon

class RepairTool(QgsProcessingAlgorithm):

    Network='Network'
    Repaired='Output'
    vAngle = 'V Node Angle'
    vDistance = 'V Node Distance'
    xNodes ='Create X Nodes'
    mIntersections = 'Multiple Intersections'
    rCircles = 'Remove Circles'
    med = 'Intermediate Step'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Repair Topology"

    def tr(self, text):
        return QCoreApplication.translate("Repair Topology", text)

    def displayName(self):
        return self.tr("Repair Topology")

    def group(self):
        return self.tr("1. Digitising")

    def shortHelpString(self):
        return self.tr("Repairs common topological erros in the digitisation of a fracture network. The tool will merge v nodes (2 endpoints) into a single linestring geometry. \n If a V Node Angle is ´specified, the algorithm will create a new line at every vertex that exceeds the given angle threshold. Apply a Distance to Extend V Nodes option to create a y node at each given v node that exceeds the given angle threshold. Select the create X nodes option to create x nodes at each given v node that exceeds the given angle threshold. In addition, the user can apply a Remove circles option, to remove all circles or loops after merging and/or extending v node linestring geometries. \n The Fix Multiple Intersections option will create a topologically consistent fracture network by sequentially removing the smallest fracture network that intersections at a location with more than 4 nodes. If a 'Fault No' attribute exists, the fracture length will be calculated based on the groupped length provided by the 'Fault No' field. \n Consider using the GRASS v.clean tool prior to the repair tool to fix a broken/corrupt feature class layer. \n Please refer to the help button for more information.")

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
        return QIcon( os.path.join( pluginPath, 'RT.jpg') )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Network"),
            [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.Repaired,
            self.tr("Repaired"),
            QgsProcessing.TypeVectorLine))

        self.addParameter(QgsProcessingParameterNumber(
            self.vDistance,
            self.tr("Distance to Extend V Nodes"),
            QgsProcessingParameterNumber.Double,
            0.0,minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.vAngle,
            self.tr("V Node Angle"),
            QgsProcessingParameterNumber.Double,
            0.0,minValue=0.0))
        self.addParameter(QgsProcessingParameterBoolean(self.xNodes,
                    self.tr("Create X Nodes"),False))
        self.addParameter(QgsProcessingParameterBoolean(self.rCircles,
                    self.tr("Remove Circles"),False))
        self.addParameter(QgsProcessingParameterBoolean(self.mIntersections,
                    self.tr("Fix Multiple Intersections"),False))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.med,
            self.tr("Multiple Intersections Repair"),
            QgsProcessing.TypeVectorLine, '',optional=True))

    def processAlgorithm(self, parameters, context, feedback):

        try:
            import networkx as nx
        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            feedback.reportError(QCoreApplication.translate('Error',' '))
            feedback.reportError(QCoreApplication.translate('Error','Error loading modules - please install the necessary dependencies'))
            return {}

        layer = self.parameterAsLayer(parameters, self.Network, context)
        M = parameters[self.mIntersections]
        X = parameters[self.xNodes]
        rC = parameters[self.rCircles]

        P = 100000000 #Precision

        infc = parameters[self.Network]

        vdistance = parameters[self.vDistance]

        angle =  parameters[self.vAngle] #Orientation Threshold
        if angle == 0.0:
            angle = 360

        if vdistance > 0: #Explode lines
            params = {'INPUT':infc,'OUTPUT':'TEMPORARY_OUTPUT'}
            explode = st.run("native:explodelines",params,context=context,feedback=feedback)
            params = {'INPUT':explode['OUTPUT'],'LINES':explode['OUTPUT'],'OUTPUT':'memory:'}
            templines = st.run('native:splitwithlines',params,context=context,feedback=feedback)
        else:
            params = {'INPUT':infc,'LINES':infc,'OUTPUT':'memory:'}
            templines = st.run('native:splitwithlines',params,context=context,feedback=feedback)


        feedback.pushInfo(QCoreApplication.translate('Nodes','Reading Node Information'))
        features = templines['OUTPUT'].getFeatures(QgsFeatureRequest())

        fields = QgsFields()
        for field in layer.fields():
            fields.append(QgsField(field.name(),field.type()))

        (writer2, dest_id2) = self.parameterAsSink(parameters, self.Repaired, context,
                                               fields, QgsWkbTypes.LineString, layer.sourceCrs())
        if M:
            if self.med not in parameters:
                feedback.reportError(QCoreApplication.translate('Node Error', 'Error - Cannot apply "Fix Multiple Intersections" without creating a new vector file. Please change the "Multiple Intersections Repair" output to an absolute path or Create temporary layer option.'))
                return {}

            (writer, dest_id) = self.parameterAsSink(parameters, self.med, context,
                                                     fields, QgsWkbTypes.LineString, layer.sourceCrs())

        fet = QgsFeature()
        Graph, W = {}, False

        for enum,feature in enumerate(features):
            try:
                geom = feature.geometry()
                if math.isnan(feature.geometry().length()): #Fix non-geometry points
                    geom = geom.asPolyline()
                    W = True
                    points = []
                    for pnt in geom:
                        if math.isnan(pnt.x()) or math.isnan(pnt.y()):
                            continue
                        points.append(QgsPointXY(pnt.x(),pnt.y()))
                    if len(points) < 2:
                        continue
                    else:
                        geom = QgsGeometry.fromPolylineXY(points).asPolyline()
                else:
                    geom = geom.asPolyline()
                if feature.geometry().length() < 0.000001:
                    continue

                start,end = geom[0],geom[-1]
                startx,starty=start
                endx,endy=end
                branch = [(math.ceil(startx*P)/P,math.ceil(starty*P)/P),(math.ceil(endx*P)/P,math.ceil(endy*P)/P)]

                for b in branch:
                    if b in Graph: #node count
                        Graph[b] += 1
                    else:
                        Graph[b] = 1

            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Node Error','%s'%(e)))
                continue
        if W:
            feedback.reportError(QCoreApplication.translate('Warning','Warning: Null geometry value found in input layer - attempting to resolve'))

        attrs = {}
        G = nx.Graph()
        feedback.pushInfo(QCoreApplication.translate('Create Lines','Creating V Node Graph'))

        total = templines['OUTPUT'].featureCount()
        total = 100.0/total

        features = templines['OUTPUT'].getFeatures(QgsFeatureRequest())
        for enum,feature in enumerate(features):
            try:
                if math.isnan(feature.geometry().length()): #Fix non-geometry points
                    geom = feature.geometry().asPolyline()
                    points = []
                    for pnt in geom:
                        if math.isnan(pnt.x()) or math.isnan(pnt.y()):
                            continue
                        points.append(QgsPointXY(pnt.x(),pnt.y()))
                    if len(points) < 2:
                        continue
                    else:
                        geom = QgsGeometry.fromPolylineXY(points)
                else:
                    geom = feature.geometry()

                if geom.length() < 0.000001:
                    continue
                if total != -1:
                    feedback.setProgress(int(enum*total))

                geom = geom.asPolyline()

                rows = []
                for field in layer.fields():
                    rows.append(feature[field.name()])

                start,end = geom[0],geom[-1]
                startx,starty=start
                endx,endy=end
                branch = [(math.ceil(startx*P)/P,math.ceil(starty*P)/P),(math.ceil(endx*P)/P,math.ceil(endy*P)/P)]

                vertices = [Graph[branch[0]],Graph[branch[1]]]
                if 2 in vertices:
                    # if fc: #Simplify branch from start to end
                    #     G.add_edge(branch[0],branch[1])
                    #     attrs[branch[0]] = rows #Keep attributes of feature
                    #     attrs[branch[1]] = rows
                    #     continue
                    # else:
                    startP = None
                    for pnt in geom:
                        pnt = (math.ceil(pnt.x()*P)/P,math.ceil(pnt.y()*P)/P)
                        if startP == None:
                            startP = pnt
                            continue
                        else:
                            endP = pnt
                            G.add_edge(startP,endP)
                            attrs[startP] = rows
                            attrs[endP] = rows
                            startP = endP
                    continue

                points = []
                for pnt in geom:
                    x,y = (math.ceil(pnt[0]*P)/P,math.ceil(pnt[1]*P)/P)
                    points.append(QgsPointXY(x,y))
                    geomFeat = QgsGeometry.fromPolylineXY(points)

                fet.setGeometry(geomFeat)
                fet.setAttributes(rows)
                writer2.addFeature(fet, QgsFeatureSink.FastInsert)

            except Exception as e:
                feedback.pushInfo(QCoreApplication.translate('Create Lines','%s'%(e)))
                break

        def calcOrient(start,end):
            startxC,startyC = start
            endxC,endyC = end
            dx,dy = endxC-startxC,endyC-startyC
            angle = math.degrees(math.atan2(dy,dx))
            bearing = (90.0 - angle) % 360
            if bearing == 0.0:
                bearing = 0.0001
            return bearing

        enum = 0
        Graph2 = []
        polyline, data= [],[]
        if len(G) > 0:
            total = 100.0/len(G)

        feedback.pushInfo(QCoreApplication.translate('Create Lines','Merging or extending v nodes'))
        for enum,node in enumerate(G.nodes()): #TO DO split polyline at Y node intersections
            feedback.setProgress(int(enum*total))
            start = node
            if start in Graph:
                v = Graph[start]
                if v > 2:
                    continue
            prevOrient,end = None,None
            enum +=1
            points = []
            while start:
                c = False
                edges = G.edges(start)
                curOrient = None
                for edge in edges:
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
                            prevOrientOrig = prevOrient
                            data.extend([line,line2])
                            end = curEnd
                            points = [QgsPointXY(curEnd[0],curEnd[1]),QgsPointXY(start[0],start[1])]
                            continue
                        if start in Graph:
                            v = Graph[start]
                            if v > 2:
                                c = False
                                break
                        curOrient = calcOrient(curEnd,start)
                        curDiff = 180 - abs(abs(prevOrient - curOrient) - 180)
                        if curDiff < angle:
                            data.extend([(start,curEnd),(curEnd,start)])
                            prevOrient = calcOrient(curEnd,start)
                            points.append(QgsPointXY(curEnd[0],curEnd[1]))
                            start = curEnd
                            c = True
                            break
                if not c:
                    start = None
                    prevOrient = prevOrientOrig
            while end:

                c = False
                edges = G.edges(end)
                for edge in edges:
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
                            data.extend([line,line2])
                            points = [QgsPointXY(curStart[0],curStart[1]),QgsPointXY(end[0],end[1])]
                            continue

                        if end in Graph:
                            v = Graph[end]
                            if v > 2:
                                c = False
                                break

                        curOrient = calcOrient(end,curStart)
                        curDiff = 180 - abs(abs(prevOrient - curOrient) - 180)
                        if curDiff < angle:
                            data.extend([(end,curStart),(curStart,end)])
                            prevOrient = calcOrient(end,curStart)
                            end = curStart
                            points.insert(0,QgsPointXY(curStart[0],curStart[1]))
                            c = True
                            break
                if not c:
                    end = None
            if points:
                polyline.append(points)

        feedback.pushInfo(QCoreApplication.translate('Create Lines','Creating Lines'))

        if len(polyline) > 0:
            total = 100.0/len(polyline)
        for enum,part in enumerate(polyline):
            if total != -1:
                feedback.setProgress(int(enum*total))
            try:
                if part:
                    outGeom = QgsGeometry.fromPolylineXY(part)
                    geom = outGeom.asPolyline()
                    start,end = geom[0],geom[-1]

                    if rC:
                        if start == end: #delete loops
                            continue

                    startx,starty=start
                    endx,endy=end
                    indexM = int(len(geom)/2)
                    midx,midy = geom[indexM]

                    rows = []
                    if (midx,midy) in attrs:
                        rows = attrs[(midx,midy)]

                    vertices = [Graph[(startx,starty)],Graph[(endx,endy)]]

                    if angle > 0 and angle != 360 and vdistance > 0:
                        if (startx,starty) not in Graph2 and vertices[0] == 2:
                            extendGeom = outGeom.extendLine(vdistance,0)
                            geom = extendGeom.asPolyline()
                            end2 = geom[0]
                            endx2,endy2=end2
                            points = [QgsPointXY(startx,starty),QgsPointXY(endx2,endy2)]
                            feedback.pushInfo(QCoreApplication.translate('Create Lines', str(points)))
                            poly = QgsGeometry.fromPolylineXY(points)
                            fet.setGeometry(poly)
                            fet.setAttributes(rows)
                            writer2.addFeature(fet,QgsFeatureSink.FastInsert)

                            if not X:
                                Graph2.append((startx,starty))

                        if (endx,endy) not in Graph2 and vertices[1] == 2:
                            extendGeom = outGeom.extendLine(0,vdistance)
                            geom = extendGeom.asPolyline()
                            start2 = geom[-1]
                            startx2,starty2=start2
                            points = [QgsPointXY(startx2,starty2),QgsPointXY(endx,endy)]
                            poly = QgsGeometry.fromPolylineXY(points)
                            fet.setGeometry(poly)
                            fet.setAttributes(rows)
                            writer2.addFeature(fet,QgsFeatureSink.FastInsert)

                            if not X:
                                Graph2.append((endx,endy))
                    fet.setGeometry(outGeom)
                    fet.setAttributes(rows)
                    writer2.addFeature(fet,QgsFeatureSink.FastInsert)
            except Exception as e:
                feedback.pushInfo(QCoreApplication.translate('Create Lines',str(e)))
                continue

        del G

        if M: #TO DO - simplify

            params = {'INPUT': dest_id2, 'LINES': dest_id2, 'OUTPUT': 'memory:'}
            outlines = st.run('native:splitwithlines', params, context=context, feedback=feedback)

            fix = {}

            feedback.pushInfo(QCoreApplication.translate('Create Lines','Repairing Multiple Intersections'))

            idx = outlines['OUTPUT'].fields().indexFromName('Fault No')
            G = nx.MultiGraph()
            lengths = {}
            Graph = {}
            for enum,feature in enumerate(outlines['OUTPUT'].getFeatures(QgsFeatureRequest())):
                if feature.geometry().length() < 0.000001:
                    continue
                geom = feature.geometry().asPolyline()
                start,end = geom[0],geom[-1]
                startx,starty=start
                endx,endy=end
                branch = [(math.ceil(startx*P)/P,math.ceil(starty*P)/P),(math.ceil(endx*P)/P,math.ceil(endy*P)/P)]
                if idx == -1:
                    FID = enum
                else:
                    FID = feature['Fault No']
                G.add_edge(branch[0],branch[1],FIDv=FID,length = feature.geometry().length())

                if FID in lengths:
                    v = lengths[FID] + feature.geometry().length()
                else:
                    v = feature.geometry().length()
                lengths[FID] = v
                for b in branch:
                    if b in Graph: #node count
                        Graph[b] += 1
                    else:
                        Graph[b] = 1

            for node in G.nodes():

                if Graph[node] > 4:
                    edges = G.edges(node,data=True)
                    fLen = []
                    for edge in edges:
                        FID = edge[2]['FIDv']
                        fLen.append(lengths[FID])

                    fLen.sort(reverse=True)
                    threshold = fLen[-1]

                    while len(fLen) > 4:
                        L = 1e10
                        for edge in edges:
                            FID = edge[2]['FIDv']
                            geomLen = edge[2]['length']
                            curfLen = lengths[FID]

                            if curfLen == threshold and geomLen < L:
                                if node == edge[0]:
                                    outNode = edge[1]
                                else:
                                    outNode = edge[0]
                                L = geomLen

                        if node in fix:
                            data = fix[node]
                            data.append(outNode)
                        else:
                            fix[node] = [outNode]
                        fLen = fLen[:-1]
                        threshold = fLen[-1]

            feedback.pushInfo(QCoreApplication.translate('Create Lines','Creating Output'))
            fet = QgsFeature()
            features = outlines['OUTPUT'].getFeatures(QgsFeatureRequest())
            for feature in features:
                if feature.geometry().length() < 0.000001:
                    continue
                geom = feature.geometry()
                geomFeat = geom.asPolyline()
                start,end = geomFeat[0],geomFeat[-1]
                startx,starty=start
                endx,endy=end
                branch = [(math.ceil(startx*P)/P,math.ceil(starty*P)/P),(math.ceil(endx*P)/P,math.ceil(endy*P)/P)]

                if branch[0] in fix:
                    data = fix[branch[0]]
                    if branch[1] in data:
                        if len(geomFeat) > 2:
                            geomFeat = geomFeat[1:]
                            geom = QgsGeometry.fromPolylineXY(geomFeat)
                        else:
                            continue
                if branch[1] in fix:
                    data = fix[branch[1]]
                    if branch[0] in data:
                        if len(geomFeat) > 2:
                            geomFeat = geomFeat[:-1]
                            geom = QgsGeometry.fromPolylineXY(geomFeat)
                        else:
                            continue
                rows = []
                for field in layer.fields():
                    rows.append(feature[field.name()])
                fet.setGeometry(geom)
                fet.setAttributes(rows)
                writer.addFeature(fet,QgsFeatureSink.FastInsert)

            return {self.Repaired:dest_id2,self.med:dest_id}
        else:
            return {self.Repaired:dest_id2}
