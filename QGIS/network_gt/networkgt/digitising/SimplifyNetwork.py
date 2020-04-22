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
from qgis.core import *
from qgis.PyQt.QtGui import QIcon

class SimplifyNetwork(QgsProcessingAlgorithm):

    Network = 'Fracture Network'
    Simple = 'Simplify'
    Simplified = 'Simplified'
    iFrac = 'Isolated Fractures'
    Dangles = 'Dangles'
    SP = 'Shortest Pathway'
    Extent = 'Extent'
    Direction = 'Direction'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Simplify Network"

    def tr(self, text):
        return QCoreApplication.translate("Simplify Network", text)

    def displayName(self):
        return self.tr("Simplify Network")

    def group(self):
        return self.tr("1. Digitising")

    def shortHelpString(self):
        return self.tr("Simplify the fracture network while maintaining the original geometry. The extent option will reduce the size of the fracture network based on the extent of another layer or a manually drawn rectangle. Based on the selected extent, the 'Select Boundary Direction' can be choosen to only preserve the dangles that touch those boundaries. 'Remove dangles' will remove all dangles or I - C branches with the exception to dangles that bound the 'Select Boundary Direction' option or manually selected dangles in the fracture network prior to executing the algorithm. 'Remove Isolated Fractures' will remove all isolated fractures of I - I branches. \n The 'Shortest Pathway' option will define all pathways from start to endpoint between the boundaries choosen in the 'Select Boundary Direction' options or between manually selected dangles in the fracture network prior to executing the algorithm. \n The 'Simplify' tool will simplify each fracture line or branch by only preserving the start and endpoint while mainting the original fracture length geometry in a new 'origLen' field. It is recommended to use this step to simplify a fracture network for 1D simulations while mainting the original fracture length geometry.\n Please refer to the help button for more information.")

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
        return QIcon( os.path.join( pluginPath, 'T.jpg') )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Branch Network"),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterExtent(self.Extent,
                    self.tr("Extent"),optional=True))

        self.addParameter(QgsProcessingParameterEnum(self.Direction, self.tr('Select Boundary Direction'), options=[self.tr("left to right"),self.tr("bottom to top")],defaultValue=0,optional=True))

        self.addParameter(QgsProcessingParameterBoolean(self.Simple,
                                self.tr("Simplify"),True))

        self.addParameter(QgsProcessingParameterBoolean(self.Dangles,
                    self.tr("Remove Dangles"),False))

        self.addParameter(QgsProcessingParameterBoolean(self.iFrac,
                            self.tr("Remove Isolated Fractures"),True))

        self.addParameter(QgsProcessingParameterBoolean(self.SP,
                    self.tr("Shortest Pathway (Slow)"),False))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.Simplified,
            self.tr("Simplified Network"),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback):

        try:
            import networkx as nx
            from itertools import combinations
        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            feedback.reportError(QCoreApplication.translate('Error',' '))
            feedback.reportError(QCoreApplication.translate('Error','Error loading modules - please install the necessary dependencies'))
            return {}

        Network = self.parameterAsLayer(parameters, self.Network, context)
        S = parameters[self.Simple]
        D = parameters[self.Dangles]
        SP = parameters[self.SP]
        I = parameters[self.iFrac]
        extent = parameters[self.Extent]
        direction = parameters[self.Direction]

        Precision = 6

        fet = QgsFeature()
        fs = QgsFields()

        skip = ['origLen']
        origFields = Network.fields()
        for field in origFields:
            if field.name() not in skip:
                fs.append( QgsField(field.name() ,field.type() ))

        fs.append(QgsField('origLen', QVariant.Double))

        (writer, dest_id) = self.parameterAsSink(parameters, self.Simplified, context,
                                            fs, QgsWkbTypes.LineString, Network.sourceCrs())

        total = 100.0/Network.featureCount()

        if extent:
            extent = extent.split(' ')[0].split(',')
            rect = QgsRectangle(float(extent[0]),float(extent[2]),float(extent[1]),float(extent[3]))
            CB = True
            if direction == 0:
                geom1 = QgsGeometry.fromPolylineXY([QgsPointXY(float(extent[0]),float(extent[2])),QgsPointXY(float(extent[0]),float(extent[3]))])
                geom2 = QgsGeometry.fromPolylineXY([QgsPointXY(float(extent[1]),float(extent[2])),QgsPointXY(float(extent[1]),float(extent[3]))])
            elif direction == 1:
                geom1 = QgsGeometry.fromPolylineXY([QgsPointXY(float(extent[0]),float(extent[2])),QgsPointXY(float(extent[1]),float(extent[2]))])
                geom2 = QgsGeometry.fromPolylineXY([QgsPointXY(float(extent[0]),float(extent[3])),QgsPointXY(float(extent[1]),float(extent[3]))])
            else:
                CB = False

            geom = QgsGeometry.fromRect(rect)

            feedback.pushInfo(QCoreApplication.translate('Model','Intersecting fracture network with extent'))
            vl = QgsVectorLayer("LineString?crs=%s"%(Network.sourceCrs().authid() ), "tempLines", "memory")
            pr = vl.dataProvider()

            for field in origFields:
                pr.addAttributes([QgsField(field.name(),field.type())])
            c = 0
            if CB:
                G = nx.MultiGraph()
                sources,targets, ids = [],[],[]
            else:
                vl.startEditing()

            for enum,feature in enumerate(Network.getFeatures()): #Build intersected graph
                try:
                    if total > 0:
                        feedback.setProgress(int(enum*total))
                    curGeom = feature.geometry()
                    if curGeom.intersects(geom):
                        outGeom = curGeom.intersection(geom)
                    else:
                        continue

                    rows = []
                    for field in origFields:
                        rows.append(feature[field.name()])

                    parts = []
                    if QgsWkbTypes.isSingleType(outGeom.wkbType()):
                        parts.append(outGeom)
                    else:
                        for part in outGeom.parts():
                            parts.append(QgsGeometry.fromPolyline(part))
                    for part in parts:
                        if CB:
                            c+=1
                            geomFeat = part.asPolyline()
                            start,end = geomFeat[0],geomFeat[-1]
                            startx,starty = (round(start.x(),Precision),round(start.y(),Precision))
                            endx,endy = (round(end.x(),Precision),round(end.y(),Precision))
                            G.add_edge((startx,starty),(endx,endy),attrs=rows,geom=part,FID=c)

                            if part.intersects(geom1):
                                sources.append((startx,starty))
                                ids.append(c)
                            if part.intersects(geom2):
                                targets.append((startx,starty))
                                ids.append(c)

                        else:
                            fet.setGeometry(part)
                            fet.setAttributes(rows)
                            pr.addFeatures([fet])

                except Exception as e:
                    feedback.reportError(QCoreApplication.translate('Model',str(e)))

            if CB:

                G2 = set()

                for source in sources:
                    for target in targets:
                        if target == source:
                            continue
                        if nx.has_path(G,source,target): #Find first connection with boundary
                            G3 = nx.descendants(G,source)
                            G2 = G2.union(G3)
                            G2.add(source)
                            break

                if len(G2) == 0:
                    feedback.reportError(QCoreApplication.translate('Model','No connection found between boundary extent'))
                    return {}

                removeNodes = []
                for node in G.nodes():
                    if node not in G2:
                        removeNodes.append(node)
                del G2,G3
                G.remove_nodes_from(removeNodes) #Remove nodes from graph that do not connect to boundary
                vl.startEditing()
                selection = []
                for enum,edge in enumerate(G.edges(data=True)):
                    data = edge[2]['attrs']
                    geom = edge[2]['geom']
                    FID = edge[2]['FID']
                    fet.setGeometry(geom)
                    fet.setAttributes(data)
                    pr.addFeatures([fet])
                    if FID in ids:
                        selection.append(enum+1) #Object ID

                vl.commitChanges()
                Network = vl

                Network.selectByIds(selection)
            else:
                vl.commitChanges()
                Network = vl

        if SP:
            G = nx.Graph()
        else:
            G = nx.MultiGraph()

        feedback.pushInfo(QCoreApplication.translate('Model','Building Graph'))
        for enum,feature in enumerate(Network.getFeatures()): #Build Graph
            try:
                if total > 0:
                    feedback.setProgress(int(enum*total))

                geom = feature.geometry()
                if geom.isMultipart():
                    geomFeat = geom.asMultiPolyline()[0]
                else:
                    geomFeat = geom.asPolyline()

                start,end = geomFeat[0],geomFeat[-1]

                startx,starty = (round(start.x(),Precision),round(start.y(),Precision))
                endx,endy = (round(end.x(),Precision),round(end.y(),Precision))

                G.add_edge((startx,starty),(endx,endy),weight=0.00001)
                if SP:
                    G.add_edge((endx,endy),(startx,starty),weight=0.00001)

            except Exception as e:
                continue


        features = Network.selectedFeatures()
        dangles,nodes,G2,paths = [],[],set(),set()

        if len(features) > 0:
            feedback.pushInfo(QCoreApplication.translate('Model','Reading dangles and clusters to keep'))
            total = 100.0/Network.selectedFeatureCount()
            for enum,feature in enumerate(features): #Find Dangles
                try:
                    if total > 0:
                        feedback.setProgress(int(enum*total))

                    geom = feature.geometry()
                    if geom.isMultipart():
                        geomFeat = geom.asMultiPolyline()[0]
                    else:
                        geomFeat = geom.asPolyline()

                    start,end = geomFeat[0],geomFeat[-1]

                    startx,starty = (round(start.x(),Precision),round(start.y(),Precision))
                    endx,endy = (round(end.x(),Precision),round(end.y(),Precision))

                    dangles.append(((startx,starty),(endx,endy)))

                except Exception as e:
                    continue
            SP_nodes = []

            for dangle in dangles:
                G3 = nx.descendants(G,dangle[0])
                G2 = G2.union(G3)
                G2.add(dangle[0])
                nodes.extend([dangle[0],dangle[1]])
                SP_nodes.append(dangle[0])
            del G3

            if SP:
                feedback.pushInfo(QCoreApplication.translate('Model','Calculating Shortest Pathways'))
                if len(dangles) < 2:
                    feedback.reportError(QCoreApplication.translate('Model','Must select a minimum of two dangles to calculate shortest pathway'))
                else:
                    cmbs = combinations(SP_nodes,2)
                    for start,end in cmbs:
                        if nx.has_path(G,start,end):
                            path = nx.shortest_path(G, source=start, target=end,weight='weight')
                            curLen = len(path)
                            while curLen != len(paths):
                                paths.update(path)
                                curLen = len(paths)
                                startp = None
                                for endp in path:
                                    if startp == None:
                                        startp = endp
                                        continue
                                    else:
                                        G[startp][endp]['weight'] = 9999 #Create a new weight along the centerline pathway
                                    startp = endp
                                path = nx.shortest_path(G, source=start, target=end,weight='weight')
                                paths.update(path)


        if D:
            curLen = 0
            G3 = G.copy()
            while len(G3) != curLen:
                curLen = len(G3)
                degree = G3.degree()
                removeNodes = [k for k,v in degree if v == 1 and k not in nodes]
                G3.remove_nodes_from(removeNodes)

        total = 100.0/Network.featureCount()

        feedback.pushInfo(QCoreApplication.translate('Model','Creating Features'))
        features = Network.getFeatures(QgsFeatureRequest())
        for enum,feature in enumerate(features): #Create Network

            try:
                if total != -1:
                    feedback.setProgress(int(enum*total))

                geom = feature.geometry()
                if geom.isMultipart():
                    geomFeat = geom.asMultiPolyline()[0]
                else:
                    geomFeat = geom.asPolyline()

                start,end = geomFeat[0],geomFeat[-1]

                startx,starty = (round(start.x(),Precision),round(start.y(),Precision))
                endx,endy = (round(end.x(),Precision),round(end.y(),Precision))
                branch =((startx,starty),(endx,endy))
                if SP:
                    if branch[0] not in paths or branch[1] not in paths:
                        continue
                else:
                    if len(dangles) > 0: #Define connected component
                        if branch[0] not in G2 and branch[1] not in G2:
                            continue

                    if D:
                        if branch[0] not in G3 or branch[1] not in G3:
                            continue

                if I:
                    if G.degree(branch[0]) == 1 and G.degree(branch[1]) == 1:
                        continue

                fLen = geom.length()

                if S:
                    points = [QgsPointXY(start.x(),start.y()),QgsPointXY(end.x(),end.y())]
                    geom = QgsGeometry.fromPolylineXY(points)

                rows = []
                for field in origFields:
                    if field.name() != 'origLen':
                        rows.append(feature[field.name()])
                rows.append(fLen)

                fet.setGeometry(geom)
                fet.setAttributes(rows)
                writer.addFeature(fet,QgsFeatureSink.FastInsert)

            except Exception as e:
                feedback.pushInfo(QCoreApplication.translate('Nodes',str(e)))
                continue

        return {self.Simplified:dest_id}
