from qgis.PyQt.QtCore import QCoreApplication
import os
from qgis.core import *
from qgis.PyQt.QtGui import QIcon

class Histogram(QgsProcessingAlgorithm):

    Network = 'Network'
    Group = 'Group Field'
    Weight = 'Weight Field'
    Mode = 'Bar Mode'
    Norm = 'Histogram Normalization'
    Cum = 'Cumulative Histogram'
    Bins = 'Number of Bins'
    minX = 'Min X axis'
    maxX = 'Max X axis'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Histogram"

    def tr(self, text):
        return QCoreApplication.translate("Histogram", text)

    def displayName(self):
        return self.tr("Histogram")

    def group(self):
        return self.tr("3. Geometry")

    def shortHelpString(self):
        return self.tr("Plots histogram plots of fracture size attributes (e.g. length, aperture, displacement). As well as choosing which attribute to plot, the user has the option to group the data (e.g. by orientation set number) and produce various histogram plots to help the user interpet and compare frequency-size distributions. \n The input data needs to be a fracture network linestring and the histogram plots are output in an external browser window. \n N.B. The network linestring must have an associated size attribute field (e.g. length, aperture, displacement).\n Please refer to the help button for more information.")

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
        return QIcon( os.path.join( pluginPath, 'H.jpg') )

    def initAlgorithm(self, config):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Fracture Network"),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterField(self.Weight,
            self.tr('Weight Field'), parentLayerParameterName=self.Network, type=QgsProcessingParameterField.Numeric,optional=True))

        self.addParameter(QgsProcessingParameterField(self.Group,
            self.tr('Group Field'), parentLayerParameterName=self.Network, type=QgsProcessingParameterField.Any,optional=True))

        param4 = QgsProcessingParameterEnum(self.Mode,
                                self.tr('Bar Mode'), options=["stack","overlay","group"],defaultValue=0)

        param5 = QgsProcessingParameterEnum(self.Norm,
                                self.tr('Histogram Normalization'), options=["","percent","probability"],defaultValue=0)

        param6 = QgsProcessingParameterEnum(self.Cum,
                                self.tr('Cumulative Histogram'), options=["False","True"],defaultValue=0)


        param7 = QgsProcessingParameterNumber(self.Bins, self.tr("Number of Bins"), QgsProcessingParameterNumber.Integer,0)
        param8 = QgsProcessingParameterNumber(self.minX, self.tr("Min X"), QgsProcessingParameterNumber.Double,0.0)
        param9 = QgsProcessingParameterNumber(self.maxX, self.tr("Max X"), QgsProcessingParameterNumber.Double,0.0)

        param4.setFlags(param4.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        param5.setFlags(param5.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        param6.setFlags(param6.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        param7.setFlags(param7.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        param8.setFlags(param8.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        param9.setFlags(param9.flags() | QgsProcessingParameterDefinition.FlagAdvanced)

        self.addParameter(param4)
        self.addParameter(param5)
        self.addParameter(param6)
        self.addParameter(param7)
        self.addParameter(param8)
        self.addParameter(param9)

    def processAlgorithm(self, parameters, context, feedback):

        try:
            import plotly.graph_objs as go
        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            feedback.reportError(QCoreApplication.translate('Error',' '))
            feedback.reportError(QCoreApplication.translate('Error','Error loading modules - please install the necessary dependencies'))
            return {}

        Network = self.parameterAsLayer(parameters, self.Network, context)

        WF = self.parameterAsString(parameters, self.Weight, context)
        G = self.parameterAsString(parameters, self.Group, context)

        #Settings

        dictN = {0:"",1:"percent",2:"probability"}
        dictC = {0:False,1:True}
        dictM = {0:"stack",1:"overlay",2:"group"}

        mode = dictM[parameters[self.Mode]]
        N = dictN[parameters[self.Norm]]
        C = dictC[parameters[self.Cum]]
        B = parameters[self.Bins]
        minX = parameters[self.minX]
        maxX = parameters[self.maxX]

        if B == 0:
            B = None

        if minX > maxX:
            feedback.reportError(QCoreApplication.translate('Error','X axis minimum must be less than maximum'))
            return {}
        op = 1
        if mode == "overlay":
            op = 0.75

        x = {}

        features = Network.selectedFeatures()
        total = Network.selectedFeatureCount()
        if len(features) == 0:
            features = Network.getFeatures()
            total = Network.featureCount()

        total = 100.0/total

        for enum,feature in enumerate(features):
            if total > 0:
                feedback.setProgress(int(enum*total))
            if G:
                ID = feature[G]
            else:
                ID = 'Data'

            if WF:
                v = feature[WF]
                if type(v) == int or type(v) == float:
                    pass
                else:
                    feedback.reportError(QCoreApplication.translate('Error','Weight field contains non numeric values - check for null values'))
                    return {}
            else:
                geom = feature.geometry()

                v = geom.length()

            if ID not in x:
                x[ID] = []

            values = x[ID]
            values.append(v)
            x[ID] = values

        traces = []

        for k,v in x.items():
            traces.append(go.Histogram(x=v,name=k,nbinsx=B, cumulative=dict(enabled=C),histnorm=N,opacity=op))

        ngtPath = 'https://raw.githubusercontent.com/BjornNyberg/NetworkGT/master/Images/NetworkGT_Logo1.png'

        if maxX > 0:
            layout = go.Layout(images=[dict(source=ngtPath,xref="paper", yref="paper", x=1.0, y=1.0,sizex=0.2, sizey=0.2, xanchor="right", yanchor="bottom")], barmode=mode,xaxis=dict(range=[minX,maxX]))
        else:
            layout = go.Layout(images=[dict(source=ngtPath,xref="paper", yref="paper", x=1.0, y=1.0,sizex=0.2, sizey=0.2, xanchor="right", yanchor="bottom")],barmode=mode)

        fig = go.Figure(data=traces, layout=layout)
        fig.show()

        return {}
