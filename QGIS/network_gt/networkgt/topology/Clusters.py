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
from qgis.core import (QgsField, QgsFeature, QgsPointXY, QgsProject,QgsProcessingParameterFileDestination, QgsProcessingParameterBoolean,QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsProcessingParameterNumber,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer)
from qgis.PyQt.QtGui import QIcon

class Clusters(QgsProcessingAlgorithm):

    Network = 'Fracture Network'
    stats = 'Calculate Statistics'
    OUTPUT = 'Output Statistics'
    Clusters = 'Output Clusters'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Clusters"

    def tr(self, text):
        return QCoreApplication.translate("Define Clusters", text)

    def displayName(self):
        return self.tr("Define Clusters")

    def group(self):
        return self.tr("4. Topology")

    def shortHelpString(self):
        return self.tr("Identifies clusters of connected fractures/branches within a fracture network. \n The input is a fracture network/branches linestring. The output adds a cluster field to the linestring attribtue table which assigns a cluster number to each fracture/branch. The user has the option to export a spreadsheet with statistics of the total length and number of branches in each cluster.\n Please refer to the help button for more information.")

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
        return QIcon( os.path.join( pluginPath, 'CL.jpg') )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Fracture Network"),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT,
                            self.tr('Statistics'),defaultValue ='',optional=True))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.Clusters,
            self.tr("Output Clusters"),
            QgsProcessing.TypeVectorLine, '',optional=True))

    def processAlgorithm(self, parameters, context, feedback):

        try:
            import pandas as pd
            import networkx as nx
            from math import ceil
        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            feedback.reportError(QCoreApplication.translate('Error',' '))
            feedback.reportError(QCoreApplication.translate('Error','Error loading modules - please install the necessary dependencies'))
            return {}

        Network = self.parameterAsLayer(parameters, self.Network, context)
        if self.OUTPUT in parameters:
            feedback.reportError(QCoreApplication.translate('Error',
                                                            str(self.OUTPUT)))
            feedback.reportError(QCoreApplication.translate('Error',
                                                            str(parameters)))
            out = parameters[self.OUTPUT]
            if out != 'TEMPORARY_OUTPUT':
                S = True
            else:
                S = False
        else:
            S = False

        if self.Clusters in parameters:
            fields = QgsFields()
            for field in Network.fields():
                if field.name() != 'Cluster':
                    fields.append(QgsField(field.name(), field.type()))

            fields.append(QgsField('Cluster', QVariant.Double))

            (writer, dest_id) = self.parameterAsSink(parameters, self.Clusters, context,
                                                     fields, QgsWkbTypes.LineString, Network.sourceCrs())
            fet = QgsFeature()

        else:
            pr = Network.dataProvider()

            if Network.fields().indexFromName('Cluster') == -1:
                pr.addAttributes([QgsField('Cluster', QVariant.Int)])
                Network.updateFields()

            idx = Network.fields().indexFromName('Cluster')

        field_check = Network.fields().indexFromName('Sample_No_')
        field_check2 = Network.fields().indexFromName('Connection')

        P = 100000
        graphs = {}
        total = 100.0/Network.featureCount()

        features = Network.selectedFeatures()
        total = Network.selectedFeatureCount()
        if len(features) == 0:
            features = Network.getFeatures()
            total = Network.featureCount()

        total = 100.0/total
        feedback.pushInfo(QCoreApplication.translate('Cluster','Building Graph'))
        for enum,feature in enumerate(features): #Build Graph
            try:

                if total > 0:
                    feedback.setProgress(int(enum*total))

                if field_check != -1:
                    ID = feature['Sample_No_']
                else:
                    ID = 1

                geom = feature.geometry()
                if geom.isMultipart():
                    data = geom.asMultiPolyline()[0]
                else:
                    data = geom.asPolyline()

                start,end = data[0],data[-1]

                startx,starty = ceil(start.x()*P)/P,ceil(start.y()*P)/P
                endx,endy = ceil(end.x()*P)/P,ceil(end.y()*P)/P

                if ID not in graphs:
                    Graph = nx.Graph()
                    graphs[ID] = Graph

                graphs[ID].add_edge((startx,starty),(endx,endy))

            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))

        feedback.pushInfo(QCoreApplication.translate('Clusters','Calculating Clusters'))

        clusters = {}
        c = 0
        total2 = 100.0/len(graphs)
        for enum,FID in enumerate(graphs):
            feedback.setProgress(int(enum*total2))
            G = graphs[FID]
            for graph in nx.connected_components(G):
                c+=1

                G2 = G.subgraph(graph).copy()

                for edge in G2.edges():
                    data = edge + (FID,)
                    clusters[data] = c

        clusterIDs = []
        branchType = []
        branchLength = []
        if self.Clusters not in parameters:
            Network.startEditing()
            feedback.pushInfo(QCoreApplication.translate('Clusters','Updating Feature Class'))

        for enum,feature in enumerate(Network.getFeatures()):
            try:
                if total > 0:
                    feedback.setProgress(int(enum*total))

                if field_check != -1:
                    ID = feature['Sample_No_']
                else:
                    ID = 1

                geom = feature.geometry()
                if geom.isMultipart():
                    data = geom.asMultiPolyline()[0]
                else:
                    data = geom.asPolyline()

                start,end = data[0],data[-1]

                startx,starty = ceil(start.x()*P)/P,ceil(start.y()*P)/P
                endx,endy = ceil(end.x()*P)/P,ceil(end.y()*P)/P

                branch = ((startx,starty),(endx,endy)) + (ID,)

                if branch not in clusters:
                    branch = ((endx,endy),(startx,starty)) + (ID,)
                try:
                    cluster = clusters[branch]
                except Exception:
                    cluster = -1
                if self.Clusters in parameters:
                    rows = []
                    for field in Network.fields():
                        if field.name() != 'Cluster':
                            rows.append(feature[field.name()])
                    rows.append(cluster)

                    fet.setGeometry(feature.geometry())
                    fet.setAttributes(rows)
                    writer.addFeature(fet, QgsFeatureSink.FastInsert)
                else:
                    rows = {idx:cluster}
                    pr.changeAttributeValues({feature.id():rows})
                if S and cluster != -1:
                    if field_check2 != -1:
                        C = feature['Connection']
                        branchType.append(C)

                    clusterIDs.append(cluster)
                    branchLength.append(feature.geometry().length())

            except Exception:
                continue
        if self.Clusters not in parameters:
            Network.commitChanges()

        if S:
            feedback.pushInfo(QCoreApplication.translate('Clusters','Creating Statistics File'))

            if field_check2 != -1:
                df = pd.DataFrame.from_dict({'Cluster':clusterIDs,'B':branchType, 'Length':branchLength})
                values = df.pivot_table(index='Cluster',columns='B',values='Length',aggfunc=['sum','count'])
            else:
                df = pd.DataFrame.from_dict({'Cluster':clusterIDs, 'Length':branchLength})
                values = df.pivot_table(index='Cluster',values='Length',aggfunc=['sum','count'])

            cols = ["{0} {1}".format(x,y) for x,y in zip(values.columns.get_level_values(0),values.columns.get_level_values(1))]
            values.columns = cols

            colNum = int(len(cols)/2)
            S = values.iloc[:,:colNum].sum(axis=1)
            C = values.iloc[:,colNum:].sum(axis=1)
            values["Sum"] = S
            values["Count"] = C
            values.fillna(0,inplace=True)
            values.to_csv(path_or_buf=out)
            if self.Clusters:
                return {'Cluster Stats': out,self.Clusters: dest_id}
            else:
                return {'Cluster Stats':out}
        else:
            if self.Clusters in parameters:
                return {self.Clusters: dest_id}
            else:
                return {}
