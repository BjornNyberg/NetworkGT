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
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature, QgsRaster,QgsProcessingParameterBoolean, QgsPointXY, QgsSpatialIndex, QgsProcessingParameterRasterLayer, QgsProcessingParameterFolderDestination, QgsProcessingParameterField, QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsProcessingParameterNumber,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer)
from qgis.PyQt.QtGui import QIcon

class ShortestPathway(QgsProcessingAlgorithm):

    Network = 'Fracture Network'
    SP ='Shorestest Pathway'
    Weight = 'Weight Field'
    Sources = 'Source Points'
    lineDen = 'Line Vertex Density'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Shortest Pathway"

    def tr(self, text):
        return QCoreApplication.translate("Shortest Pathway", text)

    def displayName(self):
        return self.tr("Shortest Pathway")

    def group(self):
        return self.tr("4. Topology")

    def shortHelpString(self):
        return self.tr("Measure the shortest geometrical pathway from a series of points or polyline vertices. If the supplied Source is a linestring geometry, distance along the fracture network is calculated as the distance from each vertex in the linestring geometry. Use the 'Line Vertex Density' option to add addtiional vertices along the linestring geometry. If the 'Weight' option is supplied, the cost distance calculator will be weighted to the given field. \n Output will produce a new feature layer with a 'Distance' field showing the distance or weighted distance from the given source points.\n Please refer to the help button for more information.")

    def groupId(self):
        return "4. Topology"

    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/wiki/4.-Topology-Analysis"

    def createInstance(self):
        return type(self)()

    def icon(self):
        n,path = 2,os.path.dirname(__file__)
        while(n):
            path=os.path.dirname(path)
            n -=1
        pluginPath = os.path.join(path,'icons')
        return QIcon( os.path.join( pluginPath, 'SP.jpg') )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Fracture Network"),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Sources,
            self.tr("Source Points or Polyline"),
            [QgsProcessing.TypeVectorPoint,QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterField(self.Weight,
                                self.tr('Weight Field'), parentLayerParameterName=self.Network, type=QgsProcessingParameterField.Numeric, optional=True))

        self.addParameter(QgsProcessingParameterNumber(self.lineDen, self.tr("Line Vertex Density"), QgsProcessingParameterNumber.Double, 0.0,optional=True))

        self.addParameter(QgsProcessingParameterFeatureSink(self.SP,self.tr("Shortest Pathway"),QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback):

        try:
            import processing as st
            import networkx as nx
        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            feedback.reportError(QCoreApplication.translate('Error',' '))
            feedback.reportError(QCoreApplication.translate('Error','Error loading modules - please install the necessary dependencies'))
            return {}

        Network = self.parameterAsLayer(parameters, self.Network, context)
        Sources = self.parameterAsLayer(parameters, self.Sources, context)
        d = parameters[self.lineDen]

        Precision = 6

        explode = st.run("native:explodelines",{'INPUT':Network,'OUTPUT':'memory:'},context=context,feedback=feedback)

        wF = parameters[self.Weight]

        fet = QgsFeature()
        fs = QgsFields()

        skip = ['Distance']
        fields = Network.fields()
        for field in fields:
            if field.name() not in skip:
                fs.append( QgsField(field.name() ,field.type() ))

        fs.append(QgsField('Distance', QVariant.Double))

        (writer, dest_id) = self.parameterAsSink(parameters, self.SP, context,
                                            fs, QgsWkbTypes.LineString, Network.sourceCrs())

        index = QgsSpatialIndex(explode['OUTPUT'].getFeatures())
        orig_data = {feature.id():feature for feature in explode['OUTPUT'].getFeatures()}

        srcs,data = [],{}

        if d > 0 and Sources.geometryType() == 1:
            params = {'INPUT':Sources,'INTERVAL':d,'OUTPUT':'memory:'}
            densify = st.run("native:densifygeometriesgivenaninterval",params,context=context,feedback=feedback)
            infc = densify['OUTPUT']
        else:
            infc = Sources

        params = {'INPUT':infc,'OUTPUT':'memory:'}  #Create nodes
        vertices = st.run('native:extractvertices',params,context=context,feedback=feedback)

        G = nx.Graph()

        feedback.pushInfo(QCoreApplication.translate('Model','Defining Source Nodes'))
        total = 100.0/vertices['OUTPUT'].featureCount()
        for enum,feature in enumerate(vertices['OUTPUT'].getFeatures()): #Find source node
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

                dx = startx - x
                dy =  starty - y
                w = math.sqrt((dx**2)+(dy**2))
                srcs.append((startx,starty)) #srcs.append((x,y))
                G.add_edge((startx,starty),(x,y),weight=w)
                G.add_edge((x,y),(startx,starty),weight=w)

            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))

        total = 100.0/explode['OUTPUT'].featureCount()

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
                    w = float(feature[wF])*feature.geometry().length()
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

        feedback.pushInfo(QCoreApplication.translate('Model','Creating Fracture Network'))
        try:
            if len(srcs) > 0:
                total = 100.0/len(srcs)
                lengths = None
                for enum,source in enumerate(srcs):
                    feedback.setProgress(int(enum*total))

                    if G.has_node(source):
                        if lengths != None:
                            lengths2 = nx.single_source_dijkstra_path_length(G,source)
                            for k in lengths2.keys():
                                if k in lengths:
                                    v = lengths2[k]
                                    v2 = lengths[k]
                                    if v < v2:
                                        lengths[k] = v
                                else:
                                    lengths[k] = lengths2[k]
                            del lengths2
                        else:
                            lengths = nx.single_source_dijkstra_path_length(G,source)

                if lengths: #if connection exists

                    for edge in G.edges():
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
                            elif (edge[0],edge[1]) in data:
                                rows = data[(edge[0],edge[1])]
                            else:
                                continue

                            midEx,midEy = midE
                            midSx,midSy = midS
                            points = [QgsPointXY(midSx,midSy),QgsPointXY(midEx,midEy)]

                            outGeom = QgsGeometry.fromPolylineXY(points)
                            fet.setGeometry(outGeom)

                            rows.extend([float(L)])

                            fet.setAttributes(rows)
                            writer.addFeature(fet)

        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))

        return {self.SP:dest_id}
