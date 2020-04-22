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
from qgis.core import (QgsField,QgsVectorFileWriter,QgsVectorLayer,QgsMultiLineString,QgsProcessingParameterField,QgsProcessingParameterBoolean, QgsFeature, QgsPointXY,QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry,QgsSpatialIndex, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty)
from qgis.PyQt.QtGui import QIcon

class ExtendTrim(QgsProcessingAlgorithm):

    Network='Network'
    Repaired='Output'
    tDistance = 'Trim Distance'
    eDistance = 'Extend Distance'
    Trim = 'Trim Dangles'
    Extend = 'Extend Dangles'
    sDistance = 'Short Isolated Fractures'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Trim and Extend"

    def tr(self, text):
        return QCoreApplication.translate("Trim and Extend", text)

    def displayName(self):
        return self.tr("Trim and Extend")

    def group(self):
        return self.tr("1. Digitising")

    def shortHelpString(self):
        return self.tr("Trim and extend tool will remove small dangles, delete short isolated fractures or extend fractures to another fracture line.\n User can select 'Short Isolated Fractures Threshold' to remove small isolated fractures (i.e. I - I branches), 'Distance to Trim Dangles' (i.e. I - C branches) or 'Distance to Extend Dangles' to connect a dangling line  (i.e. I - C Branches) to another linestring geometry. \n N.B. It is recommended to use the trim and extend functions seperately.\n Please refer to the help button for more information.")

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
            self.tr("Output"),
            QgsProcessing.TypeVectorLine))
        self.addParameter(QgsProcessingParameterNumber(
            self.sDistance,
            self.tr("Remove Short Isolated Fractures Threshold"),
            QgsProcessingParameterNumber.Double,
            0.0,minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.tDistance,
            self.tr("Distance to Trim Dangles"),
            QgsProcessingParameterNumber.Double,
            0.0,minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.eDistance,
            self.tr("Distance to Extend Dangles"),
            QgsProcessingParameterNumber.Double,
            0.0,minValue=0.0))

    def processAlgorithm(self, parameters, context, feedback):

        layer = self.parameterAsLayer(parameters, self.Network, context)

        P = 10000000 #Precision

        infc = parameters[self.Network]
        tdistance = parameters[self.tDistance]
        edistance = parameters[self.eDistance]
        sDist = parameters[self.sDistance]

        if edistance > 0 and edistance < 0.00001:
            edistance = 0.00001

        if edistance > 0  and tdistance > 0:
            feedback.reportError(QCoreApplication.translate('Nodes','It is recommended to run extend and trim functions separately')) ##TO DO fix errors caused by running both trim and extend

        params = {'INPUT':infc,'LINES':infc,'OUTPUT':'memory:'}
        templines = st.run('native:splitwithlines',params,context=context,feedback=feedback)

        feedback.pushInfo(QCoreApplication.translate('Nodes','Reading Node Information'))
        features = templines['OUTPUT'].getFeatures(QgsFeatureRequest())

        total = 0

        fields = QgsFields()
        for field in layer.fields():
            fields.append(QgsField(field.name(),field.type()))

        (writer, dest_id) = self.parameterAsSink(parameters, self.Repaired, context,
                                               fields, QgsWkbTypes.LineString, layer.sourceCrs())
        enum = 0

        def Graph_Network (features):
            Graph = {}
            for enum,feature in enumerate(features):
                try:
                    geom = feature.geometry().asPolyline()
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
                    continue
                    feedback.reportError(QCoreApplication.translate('Node Error','%s'%(e)))
            return Graph

        Graph = Graph_Network(features)

        layer = templines['OUTPUT']

        index = QgsSpatialIndex(layer.getFeatures())
        data = {feature.id():feature for feature in layer.getFeatures()}
        features = layer.getFeatures(QgsFeatureRequest())

        fet = QgsFeature()
        feedback.pushInfo(QCoreApplication.translate('Create Lines','Extending and Trimming Line Geometries'))

        if enum > 0:
            total = 100.0/enum
        else:
            total = -1

        vl = QgsVectorLayer("LineString?crs=%s"%(layer.sourceCrs().authid() ), "tempLines", "memory")
        pr = vl.dataProvider()

        fields = QgsFields()
        for field in layer.fields():
            fields.append(QgsField(field.name(),field.type()))
            pr.addAttributes([QgsField(field.name(),field.type())])

        vl.startEditing()

        for enum,feature in enumerate(features):
            try:
                if total != -1:
                    feedback.setProgress(int(enum*total))
                geomFeat = feature.geometry()
                geom = geomFeat.asPolyline()
                start,end = geom[0],geom[-1]
                startx,starty=start
                endx,endy=end
                branch = [(math.ceil(startx*P)/P,math.ceil(starty*P)/P),(math.ceil(endx*P)/P,math.ceil(endy*P)/P)]

                fID = feature.id()
                if fID not in data:
                    continue

                rows = []
                for field in layer.fields():
                    rows.append(feature[field.name()])

                ds,de = 0,0
                vertices = [Graph[branch[0]],Graph[branch[1]]]

                if sDist > 0:
                    if sum(vertices) == 2 and geomFeat.length() < sDist:
                        continue

                if tdistance > 0:
                    if 1 in vertices and geomFeat.length() < tdistance:
                        continue

                if edistance > 0:  ##TO DO Simplify Workflow Process
                    if vertices[0] == 1:
                        testGeom = geomFeat.extendLine(edistance,0)
                        near = index.nearestNeighbor(QgsPointXY(startx,starty), 10) #look for x closest lines
                        dist = 1e10
                        for nid in near:
                            value = data[nid]
                            inFID = value.id()
                            if inFID != fID:
                                id_geom = value.geometry()
                                if testGeom.intersects(id_geom):
                                    curDist = geomFeat.distance(id_geom)
                                    if curDist < dist and curDist > 0:
                                        dist = curDist
                                        ds = testGeom.intersection(id_geom)

                    if vertices[1] == 1:

                        testGeom2 = geomFeat.extendLine(0,edistance)
                        near = index.nearestNeighbor(QgsPointXY(endx,endy), 10) #look for x closest lines
                        dist = 1e10

                        for nid in near:
                            value = data[nid]
                            inFID = value.id()

                            if inFID != fID:
                                id_geom = value.geometry()
                                if testGeom2.intersects(id_geom):
                                    curDist = geomFeat.distance(id_geom)
                                    if curDist < dist and curDist > 0:
                                        dist = curDist
                                        de = testGeom2.intersection(id_geom)

                    if ds != 0:
                        try:
                            x,y = ds.asPoint()
                        except Exception:
                            x,y = ds.asMultiPoint()[0]

                        geom.insert(0,QgsPointXY(x,y))
                        ds = 0.0000001
                    if de != 0:
                        try:
                            x,y = de.asPoint()
                        except Exception:
                            x,y = de.asMultiPoint()[0]
                        geom.append(QgsPointXY(x,y))
                        de = 0.0000001

                points = []
                for pnt in geom:
                    x,y = pnt[0],pnt[1]# (math.ceil(pnt[0]*P)/P,math.ceil(pnt[1]*P)/P)
                    points.append(QgsPointXY(x,y))
##                    if len(points) == 2 and tdistance > 0:
##                        geom = QgsGeometry.fromPolylineXY(points)
##                        geomFeat = geom.extendLine(ds,de)
##                        fet.setGeometry(geomFeat)
##                        fet.setAttributes(rows)
##                        pr.addFeatures([fet])
##                        points = [QgsPointXY(x,y)]
                if points:
                    geom = QgsGeometry.fromPolylineXY(points)
                    geomFeat = geom.extendLine(ds,de)
                    fet.setGeometry(geomFeat)
                    fet.setAttributes(rows)
                    pr.addFeatures([fet])

            except Exception as e:
                continue
                feedback.pushInfo(QCoreApplication.translate('Nodes',str(e)))

        vl.commitChanges()

##        if tdistance > 0:  #TO DO increase speed of trim function
##            feedback.pushInfo(QCoreApplication.translate('Nodes','Repaining Topology of Trimmed Network'))
##            params = {'Network':vl,'Output':'memory:','V Node Distance':0,'V Node Angle':0,'Create X Nodes':False,'Resolve Multiple Intersections':False}
##            repaired = st.run("NetworkGT:Repair Topology",params,context=context,feedback=feedback)
##            params = {'INPUT':repaired['Output'],'LINES':repaired['Output'],'OUTPUT':'memory:'}
##        else:
        params = {'INPUT':vl,'LINES':vl,'OUTPUT':'memory:'}

        templines = st.run('native:splitwithlines',params,context=context,feedback=feedback)
        features = templines['OUTPUT'].getFeatures(QgsFeatureRequest())
        for enum,feature in enumerate(features): #Trim extended lines
            try:
                if total != -1:
                    feedback.setProgress(int(enum*total))
                geomFeat = feature.geometry()
                if geomFeat.length() < 0.000001:
                    continue

                rows = []
                for field in layer.fields():
                    rows.append(feature[field.name()])

                fet.setGeometry(geomFeat)
                fet.setAttributes(rows)
                writer.addFeature(fet,QgsFeatureSink.FastInsert)

            except Exception as e:
                feedback.pushInfo(QCoreApplication.translate('Nodes',str(e)))
                continue


        return {self.Repaired:dest_id}
