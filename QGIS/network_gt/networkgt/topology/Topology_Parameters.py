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

import os, warnings,tempfile,string,random
from qgis.PyQt.QtCore import QCoreApplication, QVariant

from qgis.core import *

from qgis.PyQt.QtGui import QIcon

class TopologyParameters(QgsProcessingAlgorithm):

    Sample_Area = 'Sample Area'
    Nodes = 'Nodes'
    Branches = 'Branches'
    TP = "Topology Parameters"
    Export = 'Export'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Topology Parameters"

    def tr(self, text):
        return QCoreApplication.translate("Topology Parameters", text)

    def displayName(self):
        return self.tr("Topology Parameters")

    def group(self):
        return self.tr("4. Topology")

    def shortHelpString(self):
        return self.tr("Extrats and calculates an array of topological parameters, and other network properties, for a specified sample area/contour grid. Parameters include, but are not limited to: number counts of different node and branch types, connections per branch, connections per line, average branch length, average line length, fracture intensity, dimensionless intensity. \n Required inputs are a Nodes point feature, Branches linestring and a sample area polygon/contour grid. The output is a Topology Parameters polygon/contour gird with all extracted parameters and properties provided in the attribute table. \n N.B. It is important that the nodes and branches are exracted from the same sample area polygon/contour grid used for the input. Remember that all the inputs must have the same coordinate reference system as the project.\n Please refer to the help button for more information.")

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
        return QIcon( os.path.join( pluginPath, 'TP.jpg') )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Nodes,
            self.tr("Nodes"),
            [QgsProcessing.TypeVectorPoint]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Branches,
            self.tr("Branches"),
            [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Sample_Area,
            self.tr("Sample Areas"),
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterBoolean(self.Export,
                    self.tr("Export Ternary Plot"),False))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.TP,
            self.tr("Topology Parameters"),
            QgsProcessing.TypeVectorPolygon))

    def processAlgorithm(self, parameters, context, feedback):

        try:
            import pandas as pd
            import numpy as np
        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            feedback.reportError(QCoreApplication.translate('Error',' '))
            feedback.reportError(QCoreApplication.translate('Error','Error loading modules - please install the necessary dependencies'))
            return {}

        plot = True

        try:
            import plotly
            import plotly.plotly as py
            import plotly.graph_objs as go
        except Exception:
            feedback.reportError(QCoreApplication.translate('Error','Plotting will be disabled as plotly module did not load - please install the necessary dependencies.'))
            plot = False

        Nodes = self.parameterAsSource(parameters, self.Nodes, context)
        Branches = self.parameterAsSource(parameters, self.Branches, context)
        SA = self.parameterAsSource(parameters, self.Sample_Area, context)

        warnings.simplefilter(action='ignore', category=FutureWarning)

        feedback.pushInfo(QCoreApplication.translate('TopologyParameters','Reading Data'))

        samples = []
        stotal = SA.featureCount()

        feedback.pushInfo(QCoreApplication.translate('TopologyParameters','%s Grid Samples'%(stotal)))
        stotal = 100.0/stotal

        for enum,feature in enumerate(SA.getFeatures(QgsFeatureRequest())):
            if stotal != -1:
                feedback.setProgress(int(enum*stotal))
            samples.append(feature['Sample_No_'])

        SN = []
        CLASS = []
        total = Nodes.featureCount()
        feedback.pushInfo(QCoreApplication.translate('TopologyParameters','%s Nodes'%(total)))
        total = 100.0/total
        for enum,feature in enumerate(Nodes.getFeatures(QgsFeatureRequest())):
            if total != -1:
                feedback.setProgress(int(enum*total))
            v = feature['Sample_No_']
            if v in samples:
                SN.append(v)
                CLASS.append(feature['Class'])

        df = pd.DataFrame({'Sample No.':SN, 'Class':CLASS})

        df['Nodes'] = 0

        df = df[['Sample No.','Class','Nodes']].groupby(['Sample No.','Class']).count().unstack(level=1)

        df.fillna(0,inplace=True)
        df.columns = df.columns.droplevel()

        node_columns = ['I','X','Y','E', 'U']

        for column in node_columns:
            if column not in df:
                df[column] = 0.0

        if 'Error' in df:
            del df['Error']

        df['No. Nodes'] = df.X + df.Y + df.I
        df['No. Branches'] = ((df.X*4.0) + (df.Y*3.0) + df.I)/2.0
        df['No. Lines'] = (df.Y + df.I)/2
        df['No. Connections'] = df.X + df.Y
        df['Connect/L'] = (2.0*(df.X+df.Y))/df['No. Lines']

        SN = []
        B = []
        CON = []
        LEN = []

        total = Branches.featureCount()
        feedback.pushInfo(QCoreApplication.translate('TopologyParameters','%s Branches'%(total)))
        total = 100.0/total
        for enum,feature in enumerate(Branches.getFeatures(QgsFeatureRequest())):
            if total != -1:
                feedback.setProgress(int(enum*total))
            v = feature['Sample_No_']
            if v in samples:
                SN.append(v)
                B.append(feature['Weight'])
                CON.append(feature['Connection'])
                LEN.append(feature.geometry().length())
        df2 = pd.DataFrame({'Sample No.':SN, 'Branches':B, 'Connection':CON,'Length':LEN})

        df3 = df2[['Sample No.','Branches','Connection']].groupby(['Sample No.','Connection']).sum().unstack(level=1)

        df3.fillna(0.0,inplace=True)

        df3.columns = df3.columns.droplevel()

        branch_columns = ['C - C','C - I', 'C - U','I - I','I - U','U - U']
        delete_columns = ['C - Error','Error - Error','Error - I', 'Error - U']

        for column in branch_columns:
            if column not in df3:
                df3[column] = 0.0

        for column in delete_columns:
            if column in df3:
                del df3[column]

        df2 = df2[['Sample No.','Length','Connection']].groupby(['Sample No.','Connection']).sum().unstack(level=1)
        df2.fillna(0.0,inplace=True)
        df2.columns = df2.columns.droplevel()

        for column in branch_columns:
            if column not in df2:
                df2[column] = 0.0

        for column in delete_columns:
            if column in df2:
                del df2[column]


        check = SA.fields().indexFromName('Radius')

        SN = []
        CIRC = []
        AREA = []

        for feature in SA.getFeatures(QgsFeatureRequest()):
            SN.append(feature['Sample_No_'])
            if check == -1:
                CIRC.append(feature.geometry().length())
                AREA.append(feature.geometry().area())
            else:
                CIRC.append(feature['Circ'])
                AREA.append(feature['Area'])

        df4 = pd.DataFrame({'Sample No.':SN, 'Circumference':CIRC, 'Area':AREA})

        df4.set_index('Sample No.', inplace=True)

        df3['Total Trace Length'] = df2['C - C'] + df2['C - I'] + df2['I - I'] + df2['C - U'] + df2['I - U'] + df2['U - U']
        df['Average Line Length'] = df3['Total Trace Length'] / df['No. Lines']
        df['Average Branch Length'] = df3['Total Trace Length'] / df['No. Branches']
        df['Connect/B'] = ((3.0*df.Y) + (4.0*df.X)) / df['No. Branches']
        df['Branch Freq'] = df['No. Branches'] / df4['Area']
        df['Line Freq'] = df['No. Lines'] / df4['Area']
        df['NcFreq'] = df['No. Connections'] / df4['Area']
        samples = df.index.tolist()

        df4 = df4.ix[samples]

        r = df4['Circumference']/(np.pi*2.0)

        a = np.pi*r*r
        a = df4['Area'] - a
        df['a'] = np.fabs(a.round(4))

        df['1D Intensity'] = 0.0

        df.ix[df.a==0.0,'1D Intensity'] = (df['E'] /(2.0*np.pi*r)) *(np.pi/2.0)
        del df['a']

        df['2D Intensity'] =  df3['Total Trace Length'] / df4['Area']
        df['Dimensionless Intensity'] = df['2D Intensity'] * df['Average Branch Length']

        df = pd.concat([df4,df,df3],axis=1)

        df = df[np.isfinite(df['No. Nodes'])]
        df.replace(np.inf, 0.0,inplace=True)
        df.replace(np.nan, 0.0,inplace=True)
        df = df.round(5)

        fs = QgsFields()

        fs.append(QgsField('Sample_No_', QVariant.Int))

        field_check = SA.fields().indexFromName('Radius')

        if field_check != -1:
            fs.append(QgsField('Radius', QVariant.Double))
            fs.append(QgsField('Rotation', QVariant.Double))

        for c in df:
            fs.append(QgsField(c, QVariant.Double))

        (writer, dest_id) = self.parameterAsSink(parameters, self.TP, context,
                                            fs, QgsWkbTypes.Polygon, Nodes.sourceCrs())

        feedback.pushInfo(QCoreApplication.translate('TopologyParametersOutput','Creating Output'))
        fet = QgsFeature()
        for enum,feature in enumerate(SA.getFeatures(QgsFeatureRequest())):
            if stotal != -1:
                feedback.setProgress(int(enum*stotal))
            if feature['Sample_No_'] in samples:
                fet.setGeometry(feature.geometry())
                rows = [feature['Sample_No_']]
                if field_check != -1:
                    rows.append(feature['Radius'])
                    rows.append(feature['Rotation'])
                rows.extend(df.ix[feature['Sample_No_']].tolist())
                fet.setAttributes(rows)
                writer.addFeature(fet,QgsFeatureSink.FastInsert)

        if plot:
            ID = ['Sample No. %s' %(s) for s in samples]
            iyxPlot = [go.Scatterternary(a = df['I'],b = df['Y'],c = df['X'],mode='markers',name='I + Y + X',text=ID,marker = dict(size = 15))]

            p1s = [(0,0.75,0.25),(0, 0.66666, 0.33333),(0,0.562500,0.437500),(0,0.429,0.571),(0,0.2,0.8)]
            p2s = [(0.2, 0.8, 0),(0.273,0.727,0),(0.368,0.632,0),(0.5,0.5,0),(0.692,0.308,0)]
            text = [1.0,1.2,1.4,1.6,1.8]

            for p1,p2,t in zip(p1s,p2s,text):
                iyxPlot.append(go.Scatterternary(a = [p1[1],p2[1]],b = [p1[2],p2[2]],c = [p1[0],p2[0]],name=str(t),text=str(t),marker = dict(size = 0,color='gray')))

            branchPlot = [go.Scatterternary(a = df['I - I'],b = df['C - I'],c = df['C - C'],mode='markers',name='I-I + C-I + C-C',text=ID,marker = dict(size = 15))]

            p = [(0,1,0),(0.01,0.81,0.18),(0.04,0.64,0.32),(0.09,0.49,0.42),(0.16,0.36,0.48),(0.25,0.25,0.5),
             (0.36,0.16,0.48),(0.49,0.09,0.42),(0.64,0.04,0.32),(0.81,0.01,0.18),(1,0,0)]

            x,y,z = [],[],[]
            for i in p:
                x.append(i[0])
                y.append(i[1])
                z.append(i[2])

            branchPlot.append(go.Scatterternary(a = x,b = z,c = y,name='Trend',marker = dict(size = 0,color='gray')))

            def layoutTemp(x_title,y_title,z_title):
                layout = {'ternary':dict(
                    sum=100,
                    aaxis=dict(
                        title=x_title,
                        ticksuffix='%',
                    ),
                    baxis=dict(
                        title=y_title,
                        ticksuffix='%'
                    ),
                    caxis=dict(
                        title=z_title,
                        ticksuffix='%'
                    ),),}
                return layout

            fname = ''.join(random.choice(string.ascii_lowercase) for i in range(10))
            fname2 = ''.join(random.choice(string.ascii_lowercase) for i in range(10))
            ngtPath = 'https://raw.githubusercontent.com/BjornNyberg/NetworkGT/master/Images/NetworkGT_Logo1.png'

            outDir = os.path.join(tempfile.gettempdir(),'Plotly')

            if not os.path.exists(outDir):
                os.mkdir(outDir)

            fname = os.path.join(outDir,'%s.html'%(fname))
            fname2 = os.path.join(outDir,'%s.html'%(fname2))

            lay = layoutTemp('I','Y','X')
            lay['images']= [dict(source=ngtPath,xref="paper", yref="paper", x=1.0, y=1.0,sizex=0.2, sizey=0.2, xanchor="right", yanchor="bottom")]

            fig = go.Figure(data=iyxPlot,layout=lay)
            plotly.offline.plot(fig,image='svg',filename=fname)

            lay = layoutTemp('I - I','C - I','C - C')
            lay['images']= [dict(source=ngtPath,xref="paper", yref="paper", x=1.0, y=1.0,sizex=0.2, sizey=0.2, xanchor="right", yanchor="bottom")]
            fig2 = go.Figure(data=branchPlot,layout=lay)
            plotly.offline.plot(fig2,image='svg',filename=fname2)

        self.dest_id=dest_id
        return {self.TP:dest_id}

    def postProcessAlgorithm(self, context, feedback):
        """
        PostProcessing to define the Symbology
        """
        try:
            output = QgsProcessingUtils.mapLayerFromString(self.dest_id, context)
            dirname = os.path.dirname(__file__)
            path = os.path.join(dirname,'TP.qml')
            output.loadNamedStyle(path)
            output.triggerRepaint()

        except Exception:
            pass
        return {self.TP:self.dest_id}
