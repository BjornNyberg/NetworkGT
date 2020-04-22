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
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProcessingParameterDefinition,QgsField,QgsVectorFileWriter,QgsVectorLayer,QgsMultiLineString,QgsProcessingParameterField,QgsProcessingParameterBoolean, QgsFeature, QgsPointXY,QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry,QgsSpatialIndex, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty)
from qgis.PyQt.QtGui import QIcon

class SnapNodes(QgsProcessingAlgorithm):

    Network='Network'
    Repaired='Snap I Nodes'
    Distance = 'Distance'
    Angle = 'Angle'
    dIters = 'Distance Iterations'
    nodeCount = 'Node Count'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Snap Nodes"

    def tr(self, text):
        return QCoreApplication.translate("Snap Nodes", text)

    def displayName(self):
        return self.tr("Snap Nodes")

    def group(self):
        return self.tr("1. Digitising")

    def shortHelpString(self):
        return self.tr("Snap I nodes in a fracture network within a given distance, angle and intersection type. 'Distance to Connect' defines the threshold by which to search for a new connection. The 'Angle' parameter specifies the angle of and to new linestring geometry does not vary more than the given threshold. The 'Snap Node Count' specifies which vertex node type can be connected as either 1 for I nodes, 2 for I or V nodes and 3 for I, V or Y nodes. \n 'Number of Distance Iterations' specifies the number of search distance iterations to perform as 'Distance to Connect' / 'Number of Distance Iterations'. The tool will snap to the first linestring geometry that meets the thresholds provided based on the order in the attribute table.\n Please refer to the help button for more information.")

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
        return QIcon( os.path.join( pluginPath, 'SN.jpg') )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Network"),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.Repaired,
            self.tr("Snapped Nodes"),
            QgsProcessing.TypeVectorLine))
        self.addParameter(QgsProcessingParameterNumber(
            self.Distance,
            self.tr("Distance to Connect"),
            QgsProcessingParameterNumber.Double,
            0.5,minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.Angle,
            self.tr("Angle"),
            QgsProcessingParameterNumber.Double,
            30.0,minValue=1.0))

        self.addParameter(QgsProcessingParameterNumber(self.nodeCount,
                                        self.tr('Snap Node Count'), QgsProcessingParameterNumber.Double,1.0,minValue=1.0,maxValue=3.0))

        param = QgsProcessingParameterNumber(self.dIters,
                                self.tr('Number of Distance Iterations'), QgsProcessingParameterNumber.Integer,3,minValue=1)

        # param1 = QgsProcessingParameterNumber(self.iters,
        #                         self.tr('Number of Neighbour Iterations'), QgsProcessingParameterNumber.Double,15.0,minValue=1.0)
        #
        #
        #
        # param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        # param1.setFlags(param1.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        # self.addParameter(param1)

    def processAlgorithm(self, parameters, context, feedback):

        layer = self.parameterAsLayer(parameters, self.Network, context)

        distance = parameters[self.Distance]
        angle = parameters[self.Angle] #Orientation Threshold

        Graph = {} #Store all node connections

        ## Preprocessing requirements

        params  = {'INPUT':layer,'OUTPUT':'memory:'}
        explode = st.run("native:explodelines",params,context=context,feedback=feedback)

        features = explode['OUTPUT'].getFeatures(QgsFeatureRequest())

        index = QgsSpatialIndex(explode['OUTPUT'].getFeatures())
        data = {feature.id():feature for feature in explode['OUTPUT'].getFeatures()}
        total = 0

        iN = 15#parameters[self.iters] #Number of neighbour points to search
        dI = parameters[self.dIters] #Number of distance operations to perform

        n = parameters[self.nodeCount]

        fields = QgsFields()
        for field in explode['OUTPUT'].fields():
            fields.append(QgsField(field.name(),field.type()))

        (writer, dest_id) = self.parameterAsSink(parameters, self.Repaired, context,
                                               fields, QgsWkbTypes.LineString, explode['OUTPUT'].sourceCrs())

        total = explode['OUTPUT'].featureCount()
        total = 100.0/total
        for enum,feature in enumerate(features):
            try:
                if total > 0:
                    feedback.setProgress(int(enum*total))
                try:
                    geom = feature.geometry().asPolyline()
                except Exception:
                    feedback.reportError(QCoreApplication.translate('Nodes','Only Linestring Layers Supported'))
                    return {}
                start,end = geom[0],geom[-1]
                branch = [start,end]
                for b in branch:
                    if b in Graph: #node count
                        Graph[b] += 1
                    else:
                        Graph[b] = 1

            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Node Error','%s'%(e)))

        skip = []

        def calcDist(start,end):
            startxC,startyC = start
            endxC,endyC = end
            dx,dy = endxC-startxC,endyC-startyC
            dist = math.sqrt((dx**2)+(dy**2))
            angle = math.degrees(math.atan2(dy,dx))
            bearing = (90.0 - angle) % 360
            return dist,bearing

        feedback.pushInfo(QCoreApplication.translate('Create Lines','Snapping Nodes'))

        fet = QgsFeature()
        addDist = distance/dI
        total = 100.0/dI

        for i in range(dI): #TO DO - remove unnecessary distance search iteration
            if total != -1:
                feedback.setProgress(int(i*total))
            distance += addDist
            for enum,feature in enumerate(explode['OUTPUT'].getFeatures(QgsFeatureRequest())):
                try:
                    geomFeat = feature.geometry()
                    try:
                        geom = geomFeat.asPolyline()
                    except Exception:
                        feedback.reportError(QCoreApplication.translate('Nodes','Only Linestring Layers Supported'))
                        return {}
                    start,end = geom[0],geom[-1]
                    branch = [start,end]
                    startx,starty = start
                    endx,endy = end
                    fID = feature.id()

                    vertices = [Graph[branch[0]],Graph[branch[1]]]
                    rows = []
                    for field in explode['OUTPUT'].fields():
                        rows.append(feature[field.name()])
                    dist, dist2 = 1e10,1e10

                    if vertices[0] == 1:
                        near = index.nearestNeighbor(QgsPointXY(startx,starty), iN) #look for x closest lines
                        dist = 1e10
                        for nid in near:
                            nearFeat = data[nid]
                            inFID = nearFeat.id()
                            if inFID != fID: ##TO DO SIMPLIFY##
                                try:
                                    nearGeom = nearFeat.geometry().asPolyline()
                                except Exception:
                                    nearGeom = nearFeat.geometry().asMultiPolyline()[0]
                                start2,end2 = nearGeom[0],nearGeom[-1]

                                featDist,featOrient = calcDist(end,start)
                                curDist,curOrient = calcDist(start,start2)
                                curDist2,curOrient2 = calcDist(start2,end2)
                                curDiff = 180 - abs(abs(featOrient - curOrient) - 180)
                                curDiff2 = 180 - abs(abs(curOrient - curOrient2) - 180)

                                v = Graph[start2]
                                if curDist < dist and curDiff < angle and curDiff2 < angle:

                                    if v <= n:
                                        dist = curDist
                                        outB = start2
                                        outFID = inFID

                                curDist,curOrient = calcDist(start,end2)
                                curDist2,curOrient2 = calcDist(end2,start2)
                                curDiff = 180 - abs(abs(featOrient - curOrient) - 180)
                                curDiff2 = 180 - abs(abs(curOrient - curOrient2) - 180)
                                v = Graph[end2]

                                if curDist < dist and curDiff < angle and curDiff2 < angle:
                                    if v <= n:
                                        dist = curDist
                                        outB = end2
                                        outFID = inFID

                        if dist < distance:
                            if outB in skip or start in skip:
                                continue
                            else:
                                points = [QgsPointXY(outB[0],outB[1]),QgsPointXY(startx,starty)]
                                outGeom = QgsGeometry.fromPolylineXY(points)

                                for nid in near:
                                    nearFeat = data[nid]
                                    inFID = nearFeat.id()
                                    if inFID == fID or inFID == outFID:
                                        continue
                                    else:
                                        nearGeom = nearFeat.geometry()
                                        geom = nearGeom.asPolyline()
                                        if geom[0] == outB or geom[1] == outB:
                                            continue
                                        elif outGeom.intersects(nearGeom):
                                            outB = None
                                            break
                                if outB:
                                    skip.extend([outB,start])
                                    fet.setGeometry(outGeom)
                                    fet.setAttributes(rows)
                                    writer.addFeature(fet,QgsFeatureSink.FastInsert)
                                    v = Graph[outB]
                                    Graph[outB] = v + 1


                    if vertices[1] == 1:
                        near = index.nearestNeighbor(QgsPointXY(endx,endy), iN) #look for x closest lines
                        dist2 = 1e10
                        for nid in near:
                            nearFeat = data[nid]
                            inFID = nearFeat.id()
                            if inFID != fID:
                                try:
                                    nearGeom = nearFeat.geometry().asPolyline()
                                except Exception:
                                    nearGeom = nearFeat.geometry().asMultiPolyline()[0]
                                start2,end2 = nearGeom[0],nearGeom[-1]

                                if ((start2,end)) in skip:
                                    continue

                                featDist,featOrient = calcDist(start,end)
                                curDist,curOrient = calcDist(end,start2)
                                curDist2,curOrient2 = calcDist(start2,end2)
                                curDiff = 180 - abs(abs(featOrient - curOrient) - 180)
                                curDiff2 = 180 - abs(abs(curOrient - curOrient2) - 180)

                                v = Graph[start2]
                                if curDist < dist2 and curDiff < angle and curDiff2 < angle:
                                    if v <= n:
                                        dist2 = curDist
                                        outB = start2
                                        outFID = inFID

                                curDist,curOrient = calcDist(end,end2)
                                curDist2,curOrient2 = calcDist(end2,start2)
                                curDiff = 180 - abs(abs(featOrient - curOrient) - 180)
                                curDiff2 = 180 - abs(abs(curOrient - curOrient2) - 180)

                                v = Graph[end2]
                                if curDist < dist2 and curDiff < angle and curDiff2 < angle:
                                    if v <= n:
                                        dist2 = curDist
                                        outB = end2
                                        outFID = inFID

                        if dist2 < distance:

                            if outB in skip or end in skip:
                                continue
                            else:
                                points = [QgsPointXY(outB[0],outB[1]),QgsPointXY(endx,endy)]
                                outGeom = QgsGeometry.fromPolylineXY(points)

                                for nid in near:
                                    nearFeat = data[nid]
                                    inFID = nearFeat.id()
                                    if inFID == fID or inFID == outFID:
                                        continue
                                    else:
                                        nearGeom = nearFeat.geometry()
                                        geom = nearGeom.asPolyline()
                                        if geom[0] == outB or geom[1] == outB:
                                            continue
                                        elif outGeom.intersects(nearGeom):
                                            outB = None
                                            break

                                if outB:
                                    skip.extend([outB,end])
                                    outGeom = QgsGeometry.fromPolylineXY(points)
                                    fet.setGeometry(outGeom)
                                    fet.setAttributes(rows)
                                    writer.addFeature(fet,QgsFeatureSink.FastInsert)
                                    Graph[outB] = v + 1

                except Exception as e:
                    feedback.reportError(QCoreApplication.translate('Node Error','%s'%(e)))
                    continue

        total = 100.0/enum
        for enum,feature in enumerate(explode['OUTPUT'].getFeatures(QgsFeatureRequest())):
            try:
                if total != -1:
                    feedback.setProgress(int(enum*total))
                geomFeat = feature.geometry()

                rows = []
                for field in explode['OUTPUT'].fields():
                    rows.append(feature[field.name()])

                fet.setGeometry(geomFeat)
                fet.setAttributes(rows)
                writer.addFeature(fet,QgsFeatureSink.FastInsert)

            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Node Error','%s'%(e)))
                continue
        return {self.Repaired:dest_id}
